import psycopg2
from psycopg2 import sql
import random
from datetime import datetime, timedelta
import math
import os

# ======================================================================
# UMFASSENDER GIS DUMMY-DATEN GENERATOR
# ======================================================================
# Erstellt alle notwendigen Tabellen und füllt sie mit realistischen Testdaten

class GISDummyDataGenerator:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None
        
        # Zürich Koordinaten (LV95)
        self.zurich_x = 2683000
        self.zurich_y = 1248000
        self.radius = 3000  # 3km Radius
    
    def connect(self):
        """Verbinde mit PostgreSQL"""
        self.conn = psycopg2.connect(**self.db_config)
        self.conn.autocommit = False
        print("✓ Datenbankverbindung hergestellt")
    
    def create_tables(self):
        """Erstelle alle benötigten Tabellen"""
        print("\n=== Erstelle Tabellen ===")
        
        cursor = self.conn.cursor()
        
        # Gemeindegrenzen
        cursor.execute("""
            DROP TABLE IF EXISTS gemeindegrenzen CASCADE;
            CREATE TABLE gemeindegrenzen (
                gemeinde_id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                geom GEOMETRY(Polygon, 2056)
            );
        """)
        print("✓ Tabelle gemeindegrenzen erstellt")
        
        # Quartiere
        cursor.execute("""
            DROP TABLE IF EXISTS quartiere CASCADE;
            CREATE TABLE quartiere (
                quartier_id SERIAL PRIMARY KEY,
                quartier_name VARCHAR(100),
                flaeche_ha NUMERIC,
                geom GEOMETRY(Polygon, 2056)
            );
        """)
        print("✓ Tabelle quartiere erstellt")
        
        # Gebäude
        cursor.execute("""
            DROP TABLE IF EXISTS gebaeude CASCADE;
            CREATE TABLE gebaeude (
                gebaeude_id SERIAL PRIMARY KEY,
                adresse VARCHAR(200),
                nutzung VARCHAR(50),
                baujahr INTEGER,
                anzahl_geschosse INTEGER,
                geschossflaeche_m2 NUMERIC,
                leerstandsquote NUMERIC,
                geom GEOMETRY(Polygon, 2056)
            );
        """)
        print("✓ Tabelle gebaeude erstellt")
        
        # Hochwasserzonen
        cursor.execute("""
            DROP TABLE IF EXISTS hochwasserzonen CASCADE;
            CREATE TABLE hochwasserzonen (
                id SERIAL PRIMARY KEY,
                gefahrenstufe VARCHAR(20),
                wiederkehrperiode_jahre INTEGER,
                geom GEOMETRY(Polygon, 2056)
            );
        """)
        print("✓ Tabelle hochwasserzonen erstellt")
        
        # Parzellen
        cursor.execute("""
            DROP TABLE IF EXISTS parzellen CASCADE;
            CREATE TABLE parzellen (
                id SERIAL PRIMARY KEY,
                parzellen_nr VARCHAR(50),
                eigentuemer VARCHAR(200),
                flaeche_m2 NUMERIC,
                nutzungszone VARCHAR(50),
                geom GEOMETRY(Polygon, 2056)
            );
        """)
        print("✓ Tabelle parzellen erstellt")
        
        # Bahnhöfe
        cursor.execute("""
            DROP TABLE IF EXISTS bahnhoefe CASCADE;
            CREATE TABLE bahnhoefe (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                geom GEOMETRY(Point, 2056)
            );
        """)
        print("✓ Tabelle bahnhoefe erstellt")
        
        # Hausanschlüsse
        cursor.execute("""
            DROP TABLE IF EXISTS hausanschluesse CASCADE;
            CREATE TABLE hausanschluesse (
                hausanschluss_id SERIAL PRIMARY KEY,
                adresse VARCHAR(200),
                einwohner INTEGER,
                geom GEOMETRY(Point, 2056)
            );
        """)
        print("✓ Tabelle hausanschluesse erstellt")
        
        # Erweitere werkleitungen Tabelle
        cursor.execute("""
            ALTER TABLE werkleitungen 
            ADD COLUMN IF NOT EXISTS von_knoten VARCHAR(50),
            ADD COLUMN IF NOT EXISTS zu_knoten VARCHAR(50),
            ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'aktiv';
        """)
        print("✓ Tabelle werkleitungen erweitert")
        
        # Erstelle räumliche Indizes
        tables = ['gemeindegrenzen', 'quartiere', 'gebaeude', 'hochwasserzonen', 
                 'parzellen', 'bahnhoefe', 'hausanschluesse']
        
        for table in tables:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table}_geom 
                ON {table} USING GIST(geom);
            """)
        
        self.conn.commit()
        print("✓ Alle Indizes erstellt")
    
    def generate_polygon(self, center_x, center_y, radius, num_points=8):
        """Generiere ein Polygon um einen Mittelpunkt"""
        points = []
        for i in range(num_points):
            angle = (2 * math.pi * i) / num_points
            # Füge etwas Zufall hinzu für unregelmäßige Formen
            r = radius * random.uniform(0.8, 1.2)
            x = center_x + r * math.cos(angle)
            y = center_y + r * math.sin(angle)
            points.append(f"{x} {y}")
        
        # Schließe das Polygon
        points.append(points[0])
        return f"POLYGON(({', '.join(points)}))"
    
    def populate_gemeindegrenzen(self):
        """Erstelle Gemeindegrenze (ganz Zürich)"""
        print("\n=== Fülle Gemeindegrenzen ===")
        cursor = self.conn.cursor()
        
        # Große Polygon um Zürich
        gemeinde_polygon = self.generate_polygon(
            self.zurich_x, self.zurich_y, 5000, 12
        )
        
        cursor.execute(f"""
            INSERT INTO gemeindegrenzen (name, geom)
            VALUES ('Zürich', ST_GeomFromText('{gemeinde_polygon}', 2056))
        """)
        
        self.conn.commit()
        print(f"✓ 1 Gemeindegrenze erstellt")
    
    def populate_quartiere(self):
        """Erstelle Quartiere"""
        print("\n=== Fülle Quartiere ===")
        cursor = self.conn.cursor()
        
        quartiere = [
            ('Altstadt', self.zurich_x, self.zurich_y),
            ('Industriequartier', self.zurich_x + 1000, self.zurich_y + 500),
            ('Wollishofen', self.zurich_x - 1500, self.zurich_y - 1000),
            ('Seefeld', self.zurich_x + 1500, self.zurich_y),
            ('Wipkingen', self.zurich_x - 500, self.zurich_y + 1500),
        ]
        
        for name, x, y in quartiere:
            polygon = self.generate_polygon(x, y, 800, 6)
            flaeche = random.randint(50, 200)
            
            cursor.execute(f"""
                INSERT INTO quartiere (quartier_name, flaeche_ha, geom)
                VALUES ('{name}', {flaeche}, ST_GeomFromText('{polygon}', 2056))
            """)
        
        self.conn.commit()
        print(f"✓ {len(quartiere)} Quartiere erstellt")
    
    def populate_gebaeude(self, num=200):
        """Erstelle Gebäude"""
        print(f"\n=== Fülle Gebäude ({num}) ===")
        cursor = self.conn.cursor()
        
        nutzungen = ['Wohnen', 'Gewerbe', 'Schule', 'Krankenhaus', 'Büro', 'Industrie']
        strassen = ['Hauptstrasse', 'Bahnhofstrasse', 'Seestrasse', 'Bergstrasse', 'Dorfstrasse']
        
        for i in range(num):
            x = self.zurich_x + random.randint(-self.radius, self.radius)
            y = self.zurich_y + random.randint(-self.radius, self.radius)
            
            # Kleines Polygon für Gebäude (10-30m)
            polygon = self.generate_polygon(x, y, random.randint(10, 30), 4)
            
            adresse = f"{random.choice(strassen)} {random.randint(1, 200)}"
            nutzung = random.choice(nutzungen)
            baujahr = random.randint(1850, 2024)
            geschosse = random.randint(1, 8)
            geschossflaeche = random.randint(200, 5000)
            leerstand = random.uniform(0, 15)
            
            cursor.execute(f"""
                INSERT INTO gebaeude 
                (adresse, nutzung, baujahr, anzahl_geschosse, geschossflaeche_m2, 
                 leerstandsquote, geom)
                VALUES ('{adresse}', '{nutzung}', {baujahr}, {geschosse}, 
                        {geschossflaeche}, {leerstand}, 
                        ST_GeomFromText('{polygon}', 2056))
            """)
            
            if (i + 1) % 50 == 0:
                print(f"  {i + 1} Gebäude erstellt...")
        
        self.conn.commit()
        print(f"✓ {num} Gebäude erstellt")
    
    def populate_hochwasserzonen(self):
        """Erstelle Hochwasserzonen"""
        print("\n=== Fülle Hochwasserzonen ===")
        cursor = self.conn.cursor()
        
        # Simuliere Fluss mit Hochwasserzonen
        zonen = [
            ('hoch', 30, self.zurich_x, self.zurich_y - 500, 300),
            ('mittel', 100, self.zurich_x, self.zurich_y - 500, 500),
            ('niedrig', 300, self.zurich_x, self.zurich_y - 500, 700),
        ]
        
        for gefahrenstufe, periode, x, y, radius in zonen:
            polygon = self.generate_polygon(x, y, radius, 8)
            
            cursor.execute(f"""
                INSERT INTO hochwasserzonen (gefahrenstufe, wiederkehrperiode_jahre, geom)
                VALUES ('{gefahrenstufe}', {periode}, ST_GeomFromText('{polygon}', 2056))
            """)
        
        self.conn.commit()
        print(f"✓ {len(zonen)} Hochwasserzonen erstellt")
    
    def populate_parzellen(self, num=100):
        """Erstelle Parzellen"""
        print(f"\n=== Fülle Parzellen ({num}) ===")
        cursor = self.conn.cursor()
        
        zonen = ['Wohnzone', 'Gewerbezone', 'Industriezone', 'Mischzone', 'Landwirtschaftszone']
        
        for i in range(num):
            x = self.zurich_x + random.randint(-self.radius, self.radius)
            y = self.zurich_y + random.randint(-self.radius, self.radius)
            
            polygon = self.generate_polygon(x, y, random.randint(20, 50), 6)
            parzellen_nr = f"P-{i+1:04d}"
            eigentuemer = f"Eigentümer {random.choice(['AG', 'GmbH', 'Privat'])} {i+1}"
            flaeche = random.randint(400, 3000)
            nutzungszone = random.choice(zonen)
            
            cursor.execute(f"""
                INSERT INTO parzellen (parzellen_nr, eigentuemer, flaeche_m2, nutzungszone, geom)
                VALUES ('{parzellen_nr}', '{eigentuemer}', {flaeche}, '{nutzungszone}',
                        ST_GeomFromText('{polygon}', 2056))
            """)
        
        self.conn.commit()
        print(f"✓ {num} Parzellen erstellt")
    
    def populate_bahnhoefe(self):
        """Erstelle Bahnhöfe"""
        print("\n=== Fülle Bahnhöfe ===")
        cursor = self.conn.cursor()
        
        bahnhoefe = [
            ('Zürich HB', self.zurich_x, self.zurich_y),
            ('Zürich Stadelhofen', self.zurich_x + 1200, self.zurich_y + 300),
            ('Zürich Enge', self.zurich_x - 800, self.zurich_y - 600),
            ('Zürich Oerlikon', self.zurich_x - 400, self.zurich_y + 2000),
            ('Zürich Altstetten', self.zurich_x - 2500, self.zurich_y + 500),
        ]
        
        for name, x, y in bahnhoefe:
            cursor.execute(f"""
                INSERT INTO bahnhoefe (name, geom)
                VALUES ('{name}', ST_GeomFromText('POINT({x} {y})', 2056))
            """)
        
        self.conn.commit()
        print(f"✓ {len(bahnhoefe)} Bahnhöfe erstellt")
    
    def populate_hausanschluesse(self, num=150):
        """Erstelle Hausanschlüsse"""
        print(f"\n=== Fülle Hausanschlüsse ({num}) ===")
        cursor = self.conn.cursor()
        
        for i in range(num):
            x = self.zurich_x + random.randint(-self.radius, self.radius)
            y = self.zurich_y + random.randint(-self.radius, self.radius)
            
            adresse = f"Musterstrasse {i+1}"
            einwohner = random.randint(1, 6)
            
            cursor.execute(f"""
                INSERT INTO hausanschluesse (adresse, einwohner, geom)
                VALUES ('{adresse}', {einwohner}, 
                        ST_GeomFromText('POINT({x} {y})', 2056))
            """)
        
        self.conn.commit()
        print(f"✓ {num} Hausanschlüsse erstellt")
    
    def populate_werkleitungen_network(self, num=80):
        """Erstelle Werkleitungen mit Netzwerk-Struktur"""
        print(f"\n=== Fülle Werkleitungen mit Knoten ({num}) ===")
        cursor = self.conn.cursor()
        
        # Lösche alte Testdaten
        cursor.execute("DELETE FROM werkleitungen")
        
        materials = ['PE', 'PVC', 'Grauguss', 'Stahl']
        durchmesser = [100, 150, 200, 250, 300]
        
        # Hauptverteiler als Startpunkt
        hv_x = self.zurich_x
        hv_y = self.zurich_y
        
        knoten_counter = 1
        
        for i in range(num):
            # Erstelle Leitungssegment
            x_start = hv_x + random.randint(-2000, 2000)
            y_start = hv_y + random.randint(-2000, 2000)
            
            length = random.randint(30, 150)
            angle = random.uniform(0, 360)
            x_end = x_start + length * math.cos(math.radians(angle))
            y_end = y_start + length * math.sin(math.radians(angle))
            
            leitung_id = f"L_{i+1:05d}"
            von_knoten = f"K_{knoten_counter:04d}" if i > 0 else "HV_001"
            zu_knoten = f"K_{knoten_counter+1:04d}"
            knoten_counter += 1
            
            material = random.choice(materials)
            dm = random.choice(durchmesser)
            verlegedatum = datetime.now() - timedelta(days=random.randint(0, 25000))
            
            cursor.execute(f"""
                INSERT INTO werkleitungen 
                (leitung_id, material, durchmesser, verlegedatum, bemerkung, 
                 geom, import_datum, von_knoten, zu_knoten, status)
                VALUES 
                ('{leitung_id}', '{material}', {dm}, '{verlegedatum.date()}', 
                 'Netzwerk-Test', 
                 ST_GeomFromText('LINESTRING({x_start} {y_start}, {x_end} {y_end})', 2056),
                 NOW(), '{von_knoten}', '{zu_knoten}', 'aktiv')
            """)
        
        self.conn.commit()
        print(f"✓ {num} Werkleitungen mit Knoten erstellt")
    
    def run(self):
        """Führe komplette Datengenerierung durch"""
        print("="*60)
        print("GIS DUMMY-DATEN GENERATOR")
        print("="*60)
        
        try:
            self.connect()
            self.create_tables()
            self.populate_gemeindegrenzen()
            self.populate_quartiere()
            self.populate_gebaeude(200)
            self.populate_hochwasserzonen()
            self.populate_parzellen(100)
            self.populate_bahnhoefe()
            self.populate_hausanschluesse(150)
            self.populate_werkleitungen_network(80)
            
            print("\n" + "="*60)
            print("✓ ALLE DUMMY-DATEN ERFOLGREICH ERSTELLT!")
            print("="*60)
            print("\nDu kannst jetzt die SQL-Abfragen testen:")
            print("  psql -U tomo -d basler_hofmann -f gis_queries.sql")
            
        except Exception as e:
            print(f"\n❌ FEHLER: {e}")
            self.conn.rollback()
        finally:
            if self.conn:
                self.conn.close()


if __name__ == "__main__":
    # Datenbank-Konfiguration
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'xxx'),
        'user': os.getenv('DB_USER', 'xxx'),
        'password': os.getenv('DB_PASSWORD', input('Passwort: '))
    }
    
    generator = GISDummyDataGenerator(db_config)
    generator.run()
