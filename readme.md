# 🗺️ GIS SQL Sammlung
PostgreSQL/PostGIS Queries für Geodaten-Analysen und Automatisierung.

## 📁 Dateien

- `analysis_queries_ok.sql` - 80+ PostGIS Queries für reale Anwendungsfälle
- `generate_realistic_gis_data.py` - Python Skript für Testdaten
- `generate_advanced_gis_data.py` - Python Skript für Testdaten

## 🎯 Kern-Features

### 10 Analyse-Kategorien
1. Räumliche Analyse (Gebäude in Hochwasserzonen)
2. Buffer-Analyse (Grundstücke um Bahnhöfe)  
3. Netzwerk-Analyse (Leitungsabhängigkeiten)
4. Datenqualität (Geometrie-Validierung)
5. Zeitliche Analyse (Sanierungsbedarf)
6. Routing (Kürzeste Wege)
7. Aggregation (Verdichtungsanalyse)
8. Change Detection (Datenänderungen)
9. Performance-Optimierung
10. Datenexport (INTERLIS)

### 5 Praxis-Szenarien
- Wohnstraße Versorgung
- Hochwasser Risikoanalyse
- Bahnhof Entwicklung
- Werkleitungsnetz
- Quartier Analyse

## 🚀 Schnellstart

```sql
-- Extensions aktivieren
CREATE EXTENSION postgis;

-- Dummy-Daten generieren
python generate_realistic_gis_data.py
python generate_advanced_gis_data.py

-- Queries ausführen
\i analysis_queries_ok.sql


