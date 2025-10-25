import psycopg2
import os

# ======================================================================
# REALISTISCHE GIS DUMMY-DATEN - SZENARIO-BASIERT
# ======================================================================
# Erstellt kleine, logisch zusammenhängende Szenarien statt zufälliger Daten

class RealisticGISDummyData:
    def __init__(self, db_config):
        self.db_config = db_config
        self.conn = None
        
        # Winterthur Koordinaten (LV95) - passend zur Stellenausschreibung!
        self.base_x = 2697000
        self.base_y = 1262000
    
    def connect(self):
        """Verbinde mit PostgreSQL"""
        self.conn = psycopg2.connect(**self.db_config)
        self.conn.autocommit = False
        print("✓ Datenbankverbindung hergestellt")
    
    def create_scenario_1_wohnstrasse(self):
        """
        SZENARIO 1: Wohnstraße mit realistischer Infrastruktur
        - 8 Wohnhäuser entlang einer Straße
        - Wasserleitung die alle Häuser versorgt
        - Hausanschlüsse an der Hauptleitung
        """
        print("\n=== SZENARIO 1: Wohnstraße 'Mühlengasse' ===")
        cursor = self.conn.cursor()
        
        # Straßenkoordinaten
        strasse_start_x = self.base_x
        strasse_start_y = self.base_y
        
        print("  Erstelle 8 Wohnhäuser...")
        # 8 Häuser entlang der Straße (40m Abstand)
        for i in range(8):
            haus_nr = i + 1
            x = strasse_start_x + (i * 40)
            y = strasse_start_y
            
            # Gebäude-Footprint (10x15m Rechteck)
            polygon = f"""POLYGON((
                {x} {y},
                {x+10} {y},
                {x+10} {y+15},
                {x} {y+15},
                {x} {y}
            ))"""
            
            baujahr = 1970 + (i * 5)  # Ältere Häuser am Anfang
            
            cursor.execute(f"""
                INSERT INTO gebaeude 
                (adresse, nutzung, baujahr, anzahl_geschosse, geschossflaeche_m2, 
                 leerstandsquote, geom)
                VALUES 
                ('Mühlengasse {haus_nr}', 'Wohnen', {baujahr}, 2, 300, 0,
                 ST_GeomFromText('{polygon}', 2056))
            """)
            
            # Hausanschluss vor jedem Haus
            cursor.execute(f"""
                INSERT INTO hausanschluesse (adresse, einwohner, geom)
                VALUES 
                ('Mühlengasse {haus_nr}', {2 + (i % 3)},
                 ST_GeomFromText('POINT({x+5} {y-3})', 2056))
            """)
        
        print("  Erstelle Hauptwasserleitung...")
        # Hauptwasserleitung entlang der Straße (DN 150)
        hauptleitung = f"""LINESTRING(
            {strasse_start_x-20} {strasse_start_y-5},
            {strasse_start_x+300} {strasse_start_y-5}
        )"""
        
        cursor.execute(f"""
            INSERT INTO werkleitungen 
            (leitung_id, material, durchmesser, verlegedatum, bemerkung, 
             geom, import_datum, von_knoten, zu_knoten, status)
            VALUES 
            ('L_MG_HAUPT', 'PE', 150, '1985-06-15', 
             'Hauptleitung Mühlengasse',
             ST_GeomFromText('{hauptleitung}', 2056),
             NOW(), 'HV_WINTERTHUR', 'K_MG_END', 'aktiv')
        """)
        
        print("  Erstelle Hausanschlussleitungen...")
        # Hausanschlussleitungen (kleine Leitungen von Hauptleitung zu jedem Haus)
        for i in range(8):
            haus_nr = i + 1
            x = strasse_start_x + (i * 40) + 5
            y = strasse_start_y
            
            anschluss = f"""LINESTRING(
                {x} {y-5},
                {x} {y-3}
            )"""
            
            cursor.execute(f"""
                INSERT INTO werkleitungen 
                (leitung_id, material, durchmesser, verlegedatum, bemerkung, 
                 geom, import_datum, von_knoten, zu_knoten, status)
                VALUES 
                ('L_MG_{haus_nr:02d}', 'PE', 32, '1985-08-{10+haus_nr}', 
                 'Hausanschluss Mühlengasse {haus_nr}',
                 ST_GeomFromText('{anschluss}', 2056),
                 NOW(), 'K_MG_HAUPT_{haus_nr:02d}', 'K_MG_HAUS_{haus_nr:02d}', 'aktiv')
            """)
        
        self.conn.commit()
        print("✓ Szenario 1 komplett (8 Häuser, 1 Hauptleitung, 8 Anschlüsse)")
    
    def create_scenario_2_hochwasser(self):
        """
        SZENARIO 2: Hochwassergefährdung
        - Fluss mit Hochwasserzonen
        - Gebäude teilweise in Gefahrenzone
        - Realistische Überschwemmungsgeometrie
        """
        print("\n=== SZENARIO 2: Eulach-Fluss mit Hochwassergefahr ===")
        cursor = self.conn.cursor()
        
        # Fluss verläuft von West nach Ost
        fluss_x = self.base_x + 500
        fluss_y = self.base_y + 200
        
        print("  Erstelle Hochwasserzonen entlang Eulach...")
        # Hohe Gefahr (direkt am Fluss, 30m breit)
        hochwasser_hoch = f"""POLYGON((
            {fluss_x-15} {fluss_y-200},
            {fluss_x+15} {fluss_y-200},
            {fluss_x+15} {fluss_y+200},
            {fluss_x-15} {fluss_y+200},
            {fluss_x-15} {fluss_y-200}
        ))"""
        
        cursor.execute(f"""
            INSERT INTO hochwasserzonen (gefahrenstufe, wiederkehrperiode_jahre, geom)
            VALUES ('hoch', 30, ST_GeomFromText('{hochwasser_hoch}', 2056))
        """)
        
        # Mittlere Gefahr (50m vom Fluss)
        hochwasser_mittel = f"""POLYGON((
            {fluss_x-50} {fluss_y-200},
            {fluss_x+50} {fluss_y-200},
            {fluss_x+50} {fluss_y+200},
            {fluss_x-50} {fluss_y+200},
            {fluss_x-50} {fluss_y-200}
        ))"""
        
        cursor.execute(f"""
            INSERT INTO hochwasserzonen (gefahrenstufe, wiederkehrperiode_jahre, geom)
            VALUES ('mittel', 100, ST_GeomFromText('{hochwasser_mittel}', 2056))
        """)
        
        print("  Erstelle Gebäude in verschiedenen Risikozonen...")
        # Kindergarten in hoher Gefahrenzone (problematisch!)
        cursor.execute(f"""
            INSERT INTO gebaeude 
            (adresse, nutzung, baujahr, anzahl_geschosse, geschossflaeche_m2, 
             leerstandsquote, geom)
            VALUES 
            ('Am Fluss 1', 'Schule', 1965, 1, 800, 0,
             ST_GeomFromText('POLYGON((
                {fluss_x-10} {fluss_y-20},
                {fluss_x+10} {fluss_y-20},
                {fluss_x+10} {fluss_y+20},
                {fluss_x-10} {fluss_y+20},
                {fluss_x-10} {fluss_y-20}
             ))', 2056))
        """)
        
        # Wohnhaus in mittlerer Gefahrenzone
        cursor.execute(f"""
            INSERT INTO gebaeude 
            (adresse, nutzung, baujahr, anzahl_geschosse, geschossflaeche_m2, 
             leerstandsquote, geom)
            VALUES 
            ('Uferweg 23', 'Wohnen', 1980, 3, 450, 0,
             ST_GeomFromText('POLYGON((
                {fluss_x-40} {fluss_y+50},
                {fluss_x-30} {fluss_y+50},
                {fluss_x-30} {fluss_y+65},
                {fluss_x-40} {fluss_y+65},
                {fluss_x-40} {fluss_y+50}
             ))', 2056))
        """)
        
        # Krankenhaus außerhalb Gefahrenzone (sicher)
        cursor.execute(f"""
            INSERT INTO gebaeude 
            (adresse, nutzung, baujahr, anzahl_geschosse, geschossflaeche_m2, 
             leerstandsquote, geom)
            VALUES 
            ('Spitalstrasse 1', 'Krankenhaus', 2005, 5, 8000, 0,
             ST_GeomFromText('POLYGON((
                {fluss_x-120} {fluss_y},
                {fluss_x-80} {fluss_y},
                {fluss_x-80} {fluss_y+40},
                {fluss_x-120} {fluss_y+40},
                {fluss_x-120} {fluss_y}
             ))', 2056))
        """)
        
        self.conn.commit()
        print("✓ Szenario 2 komplett (2 Hochwasserzonen, 3 Gebäude mit unterschiedlichem Risiko)")
    
    def create_scenario_3_bahnhof_entwicklung(self):
        """
        SZENARIO 3: Bahnhofsentwicklung
        - Neuer Bahnhof
        - Parzellen im Umkreis (für Verdichtungsanalyse)
        - Unterschiedliche Nutzungszonen
        """
        print("\n=== SZENARIO 3: Bahnhof Grüze mit Entwicklungspotenzial ===")
        cursor = self.conn.cursor()
        
        bahnhof_x = self.base_x + 1000
        bahnhof_y = self.base_y + 500
        
        print("  Erstelle Bahnhof...")
        cursor.execute(f"""
            INSERT INTO bahnhoefe (name, geom)
            VALUES ('Winterthur Grüze', 
                    ST_GeomFromText('POINT({bahnhof_x} {bahnhof_y})', 2056))
        """)
        
        print("  Erstelle Parzellen im Umkreis...")
        # Parzelle 1: Industriebrache (50m vom Bahnhof) - hohes Entwicklungspotenzial
        cursor.execute(f"""
            INSERT INTO parzellen (parzellen_nr, eigentuemer, flaeche_m2, nutzungszone, geom)
            VALUES 
            ('P-GRUEZE-01', 'Stadt Winterthur', 2500, 'Industriezone',
             ST_GeomFromText('POLYGON((
                {bahnhof_x+50} {bahnhof_y-30},
                {bahnhof_x+100} {bahnhof_y-30},
                {bahnhof_x+100} {bahnhof_y+20},
                {bahnhof_x+50} {bahnhof_y+20},
                {bahnhof_x+50} {bahnhof_y-30}
             ))', 2056))
        """)
        
        # Parzelle 2: Wohnzone (80m vom Bahnhof)
        cursor.execute(f"""
            INSERT INTO parzellen (parzellen_nr, eigentuemer, flaeche_m2, nutzungszone, geom)
            VALUES 
            ('P-GRUEZE-02', 'Baugenossenschaft', 1800, 'Wohnzone',
             ST_GeomFromText('POLYGON((
                {bahnhof_x-90} {bahnhof_y},
                {bahnhof_x-50} {bahnhof_y},
                {bahnhof_x-50} {bahnhof_y+40},
                {bahnhof_x-90} {bahnhof_y+40},
                {bahnhof_x-90} {bahnhof_y}
             ))', 2056))
        """)
        
        # Parzelle 3: Gewerbezone (120m vom Bahnhof)
        cursor.execute(f"""
            INSERT INTO parzellen (parzellen_nr, eigentuemer, flaeche_m2, nutzungszone, geom)
            VALUES 
            ('P-GRUEZE-03', 'Privat AG', 3200, 'Gewerbezone',
             ST_GeomFromText('POLYGON((
                {bahnhof_x-60} {bahnhof_y-120},
                {bahnhof_x} {bahnhof_y-120},
                {bahnhof_x} {bahnhof_y-60},
                {bahnhof_x-60} {bahnhof_y-60},
                {bahnhof_x-60} {bahnhof_y-120}
             ))', 2056))
        """)
        
        self.conn.commit()
        print("✓ Szenario 3 komplett (1 Bahnhof, 3 Parzellen in verschiedenen Zonen)")
    
    def create_scenario_4_leitungsnetz(self):
        """
        SZENARIO 4: Realistisches Leitungsnetz
        - Hierarchisches Netz: Hauptverteiler -> Verteilleitung -> Stichleitung
        - Realistische Durchmesser je nach Hierarchie
        - Tatsächliche Knoten-Topologie
        """
        print("\n=== SZENARIO 4: Hierarchisches Werkleitungsnetz ===")
        cursor = self.conn.cursor()
        
        netz_x = self.base_x + 1500
        netz_y = self.base_y
        
        print("  Erstelle Hauptverteiler und Transportleitung...")
        # Transportleitung vom Reservoir (DN 400)
        cursor.execute(f"""
            INSERT INTO werkleitungen 
            (leitung_id, material, durchmesser, verlegedatum, bemerkung, 
             geom, import_datum, von_knoten, zu_knoten, status)
            VALUES 
            ('L_TRANSPORT_01', 'Stahl', 400, '1978-05-10', 
             'Transportleitung vom Reservoir Lindberg',
             ST_GeomFromText('LINESTRING(
                {netz_x-500} {netz_y+1000},
                {netz_x} {netz_y}
             )', 2056),
             NOW(), 'RESERVOIR_LINDBERG', 'HV_STADTMITTE', 'aktiv')
        """)
        
        print("  Erstelle Verteilnetz (DN 200)...")
        # Verteilleitung Richtung Norden (DN 200)
        cursor.execute(f"""
            INSERT INTO werkleitungen 
            (leitung_id, material, durchmesser, verlegedatum, bemerkung, 
             geom, import_datum, von_knoten, zu_knoten, status)
            VALUES 
            ('L_VERTEIL_NORD', 'PE', 200, '1995-03-20', 
             'Verteilleitung Nord',
             ST_GeomFromText('LINESTRING(
                {netz_x} {netz_y},
                {netz_x} {netz_y+300}
             )', 2056),
             NOW(), 'HV_STADTMITTE', 'V_NORD_01', 'aktiv')
        """)
        
        # Verteilleitung Richtung Osten (DN 200)
        cursor.execute(f"""
            INSERT INTO werkleitungen 
            (leitung_id, material, durchmesser, verlegedatum, bemerkung, 
             geom, import_datum, von_knoten, zu_knoten, status)
            VALUES 
            ('L_VERTEIL_OST', 'PE', 200, '1995-03-25', 
             'Verteilleitung Ost',
             ST_GeomFromText('LINESTRING(
                {netz_x} {netz_y},
                {netz_x+400} {netz_y}
             )', 2056),
             NOW(), 'HV_STADTMITTE', 'V_OST_01', 'aktiv')
        """)
        
        print("  Erstelle Stichleitungen (DN 100)...")
        # Stichleitungen von Verteilleitung Nord
        for i in range(3):
            y_offset = 100 + (i * 100)
            cursor.execute(f"""
                INSERT INTO werkleitungen 
                (leitung_id, material, durchmesser, verlegedatum, bemerkung, 
                 geom, import_datum, von_knoten, zu_knoten, status)
                VALUES 
                ('L_STICH_N_{i+1:02d}', 'PE', 100, '2008-06-15', 
                 'Stichleitung Quartier Nord {i+1}',
                 ST_GeomFromText('LINESTRING(
                    {netz_x} {netz_y+y_offset},
                    {netz_x-150} {netz_y+y_offset}
                 )', 2056),
                 NOW(), 'V_NORD_{i+1:02d}', 'S_NORD_{i+1:02d}', 'aktiv')
            """)
        
        # Alte Leitung (Grauguss, sanierungsbedürftig)
        cursor.execute(f"""
            INSERT INTO werkleitungen 
            (leitung_id, material, durchmesser, verlegedatum, bemerkung, 
             geom, import_datum, von_knoten, zu_knoten, status)
            VALUES 
            ('L_ALT_GRAUGUSS', 'Grauguss', 150, '1925-08-10', 
             'Alte Graugussleitung - Sanierung geplant',
             ST_GeomFromText('LINESTRING(
                {netz_x+200} {netz_y-50},
                {netz_x+200} {netz_y-200}
             )', 2056),
             NOW(), 'V_OST_02', 'ALT_ENDE', 'aktiv')
        """)
        
        self.conn.commit()
        print("✓ Szenario 4 komplett (1 Transportleitung, 2 Verteilungen, 3 Stichleitungen, 1 Altleitung)")
    
    def create_scenario_5_quartier(self):
        """
        SZENARIO 5: Vollständiges Quartier
        - Quartiergrenze
        - Mehrere Gebäude innerhalb
        - Für Verdichtungsanalyse
        """
        print("\n=== SZENARIO 5: Quartier 'Neuwiesen' mit Bebauung ===")
        cursor = self.conn.cursor()
        
        quartier_x = self.base_x + 2000
        quartier_y = self.base_y + 1000
        
        print("  Erstelle Quartiergrenze...")
        quartier_polygon = f"""POLYGON((
            {quartier_x} {quartier_y},
            {quartier_x+400} {quartier_y},
            {quartier_x+400} {quartier_y+300},
            {quartier_x} {quartier_y+300},
            {quartier_x} {quartier_y}
        ))"""
        
        cursor.execute(f"""
            INSERT INTO quartiere (quartier_name, flaeche_ha, geom)
            VALUES ('Neuwiesen', 12.0, ST_GeomFromText('{quartier_polygon}', 2056))
        """)
        
        print("  Erstelle Bebauung im Quartier...")
        # Altbauten (vor 1950)
        for i in range(4):
            x = quartier_x + 50 + (i * 80)
            y = quartier_y + 50
            
            cursor.execute(f"""
                INSERT INTO gebaeude 
                (adresse, nutzung, baujahr, anzahl_geschosse, geschossflaeche_m2, 
                 leerstandsquote, geom)
                VALUES 
                ('Neuwiesenstrasse {(i+1)*2}', 'Wohnen', {1920 + (i*5)}, 3, 400, {5 + i},
                 ST_GeomFromText('POLYGON((
                    {x} {y}, {x+12} {y}, {x+12} {y+20}, {x} {y+20}, {x} {y}
                 ))', 2056))
            """)
        
        # Neubauten (nach 2000) - höher, mehr Geschossfläche
        for i in range(2):
            x = quartier_x + 100 + (i * 150)
            y = quartier_y + 200
            
            cursor.execute(f"""
                INSERT INTO gebaeude 
                (adresse, nutzung, baujahr, anzahl_geschosse, geschossflaeche_m2, 
                 leerstandsquote, geom)
                VALUES 
                ('Neuwiesenpark {i+1}', 'Wohnen', {2015 + (i*3)}, 5, 1200, 0,
                 ST_GeomFromText('POLYGON((
                    {x} {y}, {x+25} {y}, {x+25} {y+30}, {x} {y+30}, {x} {y}
                 ))', 2056))
            """)
        
        self.conn.commit()
        print("✓ Szenario 5 komplett (1 Quartier, 4 Altbauten, 2 Neubauten)")
    
    def run(self):
        """Führe alle Szenarien aus"""
        print("="*70)
        print("REALISTISCHE GIS DUMMY-DATEN - SZENARIO-BASIERT")
        print("="*70)
        print("\nDiese Daten ergeben räumlich und fachlich Sinn!")
        print("Perfekt für Portfolio und Bewerbung.\n")
        
        try:
            self.connect()
            self.create_scenario_1_wohnstrasse()
            self.create_scenario_2_hochwasser()
            self.create_scenario_3_bahnhof_entwicklung()
            self.create_scenario_4_leitungsnetz()
            self.create_scenario_5_quartier()
            
            print("\n" + "="*70)
            print("✓ ALLE SZENARIEN ERFOLGREICH ERSTELLT!")
            print("="*70)
            print("\nDu hast jetzt:")
            print("  • Szenario 1: Wohnstraße mit realistischer Ver- und Entsorgung")
            print("  • Szenario 2: Hochwassergefährdung mit betroffenen Gebäuden")
            print("  • Szenario 3: Bahnhofsentwicklung für Verdichtungsanalysen")
            print("  • Szenario 4: Hierarchisches Werkleitungsnetz")
            print("  • Szenario 5: Komplettes Quartier mit Bebauungsstruktur")
            print("\nJetzt kannst du sinnvolle SQL-Analysen durchführen!")
            
        except Exception as e:
            print(f"\n❌ FEHLER: {e}")
            if self.conn:
                self.conn.rollback()
        finally:
            if self.conn:
                self.conn.close()


if __name__ == "__main__":
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'xxx'),
        'user': os.getenv('DB_USER', 'xxx'),
        'password': os.getenv('DB_PASSWORD', input('PostgreSQL Passwort: '))
    }
    
    generator = RealisticGISDummyData(db_config)
    generator.run()
