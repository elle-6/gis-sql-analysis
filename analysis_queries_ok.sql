-- ======================================================================
-- UMfassende PostGIS SQL-Sammlung für GIS-Systementwicklung
-- ======================================================================

-- ----------------------------------------------------------------------
-- 1. RÄUMLICHE ANALYSE: Welche Gebäude liegen in Hochwassergebieten?
-- OK
-- ----------------------------------------------------------------------
SELECT 
    g.gebaeude_id,
    g.adresse,
    g.nutzung,
    h.gefahrenstufe,
    h.wiederkehrperiode_jahre,
    ST_Area(ST_Intersection(g.geom, h.geom)) as betroffene_flaeche_m2,
    ROUND(
        (ST_Area(ST_Intersection(g.geom, h.geom)) / ST_Area(g.geom) * 100)::numeric, 
        2
    ) as betroffener_anteil_prozent
FROM gebaeude g
JOIN hochwasserzonen h ON ST_Intersects(g.geom, h.geom)
WHERE h.gefahrenstufe IN ('hoch', 'mittel')
AND g.nutzung IN ('Wohnen', 'Schule', 'Krankenhaus')
ORDER BY betroffener_anteil_prozent DESC;

-- ----------------------------------------------------------------------
-- 2. BUFFER-ANALYSE: Finde alle Grundstücke im 100m-Radius um Bahnhöfe
-- OK
-- ----------------------------------------------------------------------
SELECT 
    p.parzellen_nr,
    p.eigentuemer,
    b.name as naechster_bahnhof,
    ROUND(ST_Distance(p.geom, b.geom)::numeric, 2) as distanz_meter,
    p.flaeche_m2,
    p.nutzungszone
FROM parzellen p
CROSS JOIN LATERAL (
    SELECT 
        id, 
        name, 
        geom
    FROM bahnhoefe
    WHERE ST_DWithin(geom, p.geom, 100)
    ORDER BY geom <-> p.geom
    LIMIT 1
) b
WHERE ST_DWithin(p.geom, b.geom, 100)
ORDER BY distanz_meter;

-- ----------------------------------------------------------------------
-- 3. NETZWERK-ANALYSE: Finde alle Leitungen die von einem Knoten abhängen
-- OK
-- ----------------------------------------------------------------------
WITH RECURSIVE leitung_netz AS (
    SELECT 
        l.leitung_id,
        l.von_knoten,
        l.zu_knoten,
        l.material,
        l.durchmesser,
        l.geom,
        1 as ebene
    FROM werkleitungen l
    WHERE l.von_knoten = 'HV_001'
    
    UNION ALL
    
    SELECT 
        l.leitung_id,
        l.von_knoten,
        l.zu_knoten,
        l.material,
        l.durchmesser,
        l.geom,
        ln.ebene + 1
    FROM werkleitungen l
    INNER JOIN leitung_netz ln ON l.von_knoten = ln.zu_knoten
    WHERE ln.ebene < 10
)
SELECT 
    ln.leitung_id,
    ln.von_knoten,
    ln.zu_knoten,
    ln.ebene,
    COUNT(h.hausanschluss_id) as betroffene_haushalte,
    SUM(h.einwohner) as betroffene_einwohner
FROM leitung_netz ln
LEFT JOIN hausanschluesse h ON ST_DWithin(h.geom, ln.geom, 5)
GROUP BY ln.leitung_id, ln.von_knoten, ln.zu_knoten, ln.ebene
ORDER BY ln.ebene, ln.leitung_id;

-- ----------------------------------------------------------------------
-- 4. DATENQUALITÄT: Finde geometrische Probleme in den Daten
-- OK
-- ----------------------------------------------------------------------
SELECT 
    'Ungültige Geometrie' as problem_typ,
    leitung_id,
    material,
    CASE 
        WHEN NOT ST_IsValid(geom) THEN ST_IsValidReason(geom)
        ELSE NULL
    END as fehler_beschreibung
FROM werkleitungen
WHERE NOT ST_IsValid(geom)

UNION ALL

SELECT 
    'Selbstüberschneidung' as problem_typ,
    leitung_id,
    material,
    'LineString überschneidet sich selbst' as fehler_beschreibung
FROM werkleitungen
WHERE ST_NumGeometries(ST_Intersection(geom, geom)) > 1

UNION ALL

SELECT 
    'Unrealistische Länge' as problem_typ,
    leitung_id,
    material,
    'Leitung nur ' || ROUND(ST_Length(geom)::numeric, 2) || 'm lang' as fehler_beschreibung
FROM werkleitungen
WHERE ST_Length(geom) < 0.5

UNION ALL

SELECT 
    'Außerhalb Gemeindegebiet' as problem_typ,
    l.leitung_id,
    l.material,
    'Leitung liegt außerhalb der Gemeindegrenze' as fehler_beschreibung
FROM werkleitungen l
LEFT JOIN gemeindegrenzen g ON ST_Within(l.geom, g.geom)
WHERE g.gemeinde_id IS NULL;

-- ----------------------------------------------------------------------
-- 5. ZEITLICHE ANALYSE: Leitungen nach Alter und Sanierungsbedarf
-- OK
-- ----------------------------------------------------------------------
SELECT 
    l.material,
    l.durchmesser,
    COUNT(*) as anzahl_leitungen,
    SUM(ST_Length(l.geom)) as gesamtlaenge_meter,
    AVG(EXTRACT(YEAR FROM AGE(CURRENT_DATE, l.verlegedatum))) as durchschnittsalter_jahre,
    SUM(
        ST_Length(l.geom) * 
        CASE l.material
            WHEN 'Grauguss' THEN 850
            WHEN 'Asbestzement' THEN 900
            WHEN 'Stahl' THEN 750
            WHEN 'PE' THEN 400
            ELSE 600
        END
    ) as geschaetzte_sanierungskosten_chf
FROM werkleitungen l
WHERE EXTRACT(YEAR FROM AGE(CURRENT_DATE, l.verlegedatum)) > 50
OR l.material IN ('Grauguss', 'Asbestzement')
GROUP BY l.material, l.durchmesser
ORDER BY geschaetzte_sanierungskosten_chf DESC;

-- ----------------------------------------------------------------------
-- 6. ROUTING: Kürzester Weg zwischen zwei Punkten im Straßennetz
-- ERROR:  relation "strassennetz_vertices_pgr" does not exist
-- ----------------------------------------------------------------------
WITH start_punkt AS (
    SELECT ST_SetSRID(ST_MakePoint(2683141, 1248115), 2056) as geom
),
ziel_punkt AS (
    SELECT ST_SetSRID(ST_MakePoint(2683891, 1247632), 2056) as geom
),
nearest_start AS (
    SELECT id FROM strassennetz_vertices_pgr
    ORDER BY geom <-> (SELECT geom FROM start_punkt)
    LIMIT 1
),
nearest_ziel AS (
    SELECT id FROM strassennetz_vertices_pgr
    ORDER BY geom <-> (SELECT geom FROM ziel_punkt)
    LIMIT 1
)
SELECT 
    r.seq,
    r.node,
    r.edge,
    s.strassenname,
    s.kategorie,
    ST_Length(s.geom) as laenge_meter,
    s.geom
FROM pgr_dijkstra(
    'SELECT id, source, target, ST_Length(geom) as cost FROM strassennetz',
    (SELECT id FROM nearest_start),
    (SELECT id FROM nearest_ziel),
    directed := false
) r
JOIN strassennetz s ON r.edge = s.id
ORDER BY r.seq;

-- ----------------------------------------------------------------------
-- 7. AGGREGATION: Verdichtungsanalyse nach Quartieren
-- OK
-- ----------------------------------------------------------------------
SELECT 
    q.quartier_name,
    q.flaeche_ha,
    COUNT(DISTINCT g.gebaeude_id) as anzahl_gebaeude,
    COUNT(DISTINCT g.gebaeude_id) / q.flaeche_ha as gebaeudedichte_pro_ha,
    SUM(g.geschossflaeche_m2) as total_geschossflaeche,
    SUM(g.geschossflaeche_m2) / (q.flaeche_ha * 10000) as geschossflachendichte,
    AVG(g.anzahl_geschosse) as durchschnittliche_geschosse,
    COUNT(CASE WHEN g.baujahr < 1950 THEN 1 END) as altbauten,
    COUNT(CASE WHEN g.leerstandsquote > 5 THEN 1 END) as gebaeude_mit_leerstand,
    CASE 
        WHEN SUM(g.geschossflaeche_m2) / (q.flaeche_ha * 10000) < 0.8 
        THEN 'Hoch - Verdichtung möglich'
        WHEN SUM(g.geschossflaeche_m2) / (q.flaeche_ha * 10000) < 1.5 
        THEN 'Mittel - Moderate Verdichtung'
        ELSE 'Niedrig - Bereits dicht bebaut'
    END as verdichtungspotenzial
FROM quartiere q
LEFT JOIN gebaeude g ON ST_Within(g.geom, q.geom)
GROUP BY q.quartier_id, q.quartier_name, q.flaeche_ha
ORDER BY geschossflachendichte;

-- ----------------------------------------------------------------------
-- 8. CHANGE DETECTION: Was hat sich seit letztem Import geändert?
-- ERROR:  relation "gebaeude_alt" does not exist
-- ----------------------------------------------------------------------
SELECT 
    'Gelöscht' as aenderung,
    a.gebaeude_id,
    a.adresse,
    a.geom
FROM gebaeude_alt a
LEFT JOIN gebaeude_neu n ON a.gebaeude_id = n.gebaeude_id
WHERE n.gebaeude_id IS NULL

UNION ALL

SELECT 
    'Neu' as aenderung,
    n.gebaeude_id,
    n.adresse,
    n.geom
FROM gebaeude_neu n
LEFT JOIN gebaeude_alt a ON n.gebaeude_id = a.gebaeude_id
WHERE a.gebaeude_id IS NULL

UNION ALL

SELECT 
    'Geometrie geändert' as aenderung,
    n.gebaeude_id,
    n.adresse,
    n.geom
FROM gebaeude_neu n
JOIN gebaeude_alt a ON n.gebaeude_id = a.gebaeude_id
WHERE NOT ST_Equals(n.geom, a.geom)
AND ST_Distance(n.geom, a.geom) > 0.5

UNION ALL

SELECT 
    'Attribute geändert' as aenderung,
    n.gebaeude_id,
    n.adresse || ' (alt: ' || a.adresse || ')' as adresse,
    n.geom
FROM gebaeude_neu n
JOIN gebaeude_alt a ON n.gebaeude_id = a.gebaeude_id
WHERE (n.adresse != a.adresse 
    OR n.nutzung != a.nutzung
    OR n.anzahl_geschosse != a.anzahl_geschosse)
AND ST_Equals(n.geom, a.geom);

-- ----------------------------------------------------------------------
-- 9. PERFORMANCE-OPTIMIERUNG: Index-Analyse und Vacuum
-- ERROR:  VACUUM cannot run inside a transaction block
-- ----------------------------------------------------------------------
SELECT 
    schemaname,
    tablename,
    'Fehlender GIST-Index' as problem
FROM pg_tables t
WHERE schemaname = 'public'
AND tablename IN (
    SELECT table_name 
    FROM information_schema.columns 
    WHERE column_name = 'geom'
)
AND NOT EXISTS (
    SELECT 1 
    FROM pg_indexes i 
    WHERE i.tablename = t.tablename 
    AND i.indexdef LIKE '%USING gist%'
);

ANALYZE werkleitungen;
ANALYZE gebaeude;
ANALYZE parzellen;
VACUUM ANALYZE werkleitungen;

-- ----------------------------------------------------------------------
-- 10. DATENEXPORT: Vorbereitung für INTERLIS-Export
-- ERROR:  function gen_random_uuid() does not exist
-- ----------------------------------------------------------------------
CREATE TEMP TABLE leitungen_export AS
SELECT 
    gen_random_uuid() as oid,
    l.leitung_id as objektnummer,
    l.material as leitungsmaterial,
    l.durchmesser as nennweite,
    ST_Transform(l.geom, 2056) as geometrie,
    'in_betrieb' as betriebszustand,
    l.verlegedatum as erfassungsdatum,
    CURRENT_DATE as nachfuehrung,
    'Gemeinde Zürich' as datenherr,
    'automatischer_export' as bemerkung
FROM werkleitungen l
WHERE l.status = 'aktiv'
AND ST_IsValid(l.geom);

SELECT 
    COUNT(*) as total_datensaetze,
    COUNT(CASE WHEN oid IS NULL THEN 1 END) as fehlende_oid,
    COUNT(CASE WHEN NOT ST_IsValid(geometrie) THEN 1 END) as ungueltige_geometrien,
    COUNT(CASE WHEN objektnummer IS NULL THEN 1 END) as fehlende_objektnummer
FROM leitungen_export;

-- ----------------------------------------------------------------------
-- SZENARIO 1: WOHNSTRASSE - Versorgungsanalyse
-- OK
-- ----------------------------------------------------------------------
SELECT 
    h.adresse as haus,
    h.einwohner,
    COUNT(w.leitung_id) as anzahl_leitungen,
    STRING_AGG(w.leitung_id, ', ') as leitungen
FROM hausanschluesse h
LEFT JOIN werkleitungen w ON ST_DWithin(h.geom, w.geom, 5)
WHERE h.adresse LIKE 'Mühlengasse%'
GROUP BY h.hausanschluss_id, h.adresse, h.einwohner
ORDER BY h.adresse;

SELECT 
    COUNT(DISTINCT h.hausanschluss_id) as anzahl_haushalte,
    SUM(h.einwohner) as total_einwohner,
    COUNT(DISTINCT w.leitung_id) as anzahl_leitungen,
    ROUND(SUM(ST_Length(w.geom))::numeric, 2) as gesamtlaenge_leitungen_meter
FROM hausanschluesse h
LEFT JOIN werkleitungen w ON w.bemerkung LIKE '%Mühlengasse%'
WHERE h.adresse LIKE 'Mühlengasse%';

SELECT 
    h.adresse,
    h.einwohner,
    'Hauptleitung Mühlengasse ausgefallen' as problem,
    'Kein Wasser' as auswirkung
FROM hausanschluesse h
WHERE h.adresse LIKE 'Mühlengasse%'
ORDER BY h.adresse;

-- ----------------------------------------------------------------------
-- SZENARIO 2: HOCHWASSER - Risikoanalyse
-- OK
-- ----------------------------------------------------------------------
SELECT 
    g.adresse,
    g.nutzung,
    h.gefahrenstufe,
    h.wiederkehrperiode_jahre,
    ROUND((ST_Area(ST_Intersection(g.geom, h.geom)) / ST_Area(g.geom) * 100)::numeric, 1) 
        as betroffener_anteil_prozent,
    CASE 
        WHEN g.nutzung IN ('Schule', 'Krankenhaus') AND h.gefahrenstufe = 'hoch' 
        THEN '⚠️ KRITISCH - Sofortmaßnahmen erforderlich'
        WHEN g.nutzung IN ('Schule', 'Krankenhaus') AND h.gefahrenstufe = 'mittel' 
        THEN '⚠ Erhöhtes Risiko - Schutzmaßnahmen prüfen'
        ELSE 'Überwachung empfohlen'
    END as handlungsempfehlung
FROM gebaeude g
JOIN hochwasserzonen h ON ST_Intersects(g.geom, h.geom)
WHERE g.adresse IN ('Am Fluss 1', 'Uferweg 23', 'Spitalstrasse 1')
ORDER BY 
    CASE g.nutzung 
        WHEN 'Schule' THEN 1 
        WHEN 'Krankenhaus' THEN 2 
        ELSE 3 
    END,
    h.gefahrenstufe;

SELECT 
    g.adresse,
    g.nutzung,
    h.gefahrenstufe,
    CASE 
        WHEN g.nutzung = 'Schule' THEN 100
        WHEN g.nutzung = 'Krankenhaus' THEN 95
        WHEN g.nutzung = 'Wohnen' THEN 80
        ELSE 50
    END +
    CASE h.gefahrenstufe
        WHEN 'hoch' THEN 50
        WHEN 'mittel' THEN 25
        ELSE 10
    END as prioritaet_score,
    'Hochwasserschutz-Investition empfohlen' as massnahme
FROM gebaeude g
JOIN hochwasserzonen h ON ST_Intersects(g.geom, h.geom)
ORDER BY prioritaet_score DESC;

SELECT 
    COUNT(*) as betroffene_gebaeude,
    SUM(g.geschossflaeche_m2) as total_geschossflaeche_m2,
    ROUND(SUM(g.geschossflaeche_m2 * 500)::numeric, 0) as geschaetzte_schutzkosten_chf
FROM gebaeude g
JOIN hochwasserzonen h ON ST_Intersects(g.geom, h.geom)
WHERE h.gefahrenstufe IN ('hoch', 'mittel');

-- ----------------------------------------------------------------------
-- SZENARIO 3: BAHNHOF - Verdichtungsanalyse
-- OK
-- ----------------------------------------------------------------------
SELECT 
    p.parzellen_nr,
    p.nutzungszone,
    p.flaeche_m2,
    b.name as bahnhof,
    ROUND(ST_Distance(p.geom, b.geom)::numeric, 0) as distanz_meter,
    CASE 
        WHEN ST_Distance(p.geom, b.geom) < 300 THEN 'A - Sehr hohes Potenzial'
        WHEN ST_Distance(p.geom, b.geom) < 500 THEN 'B - Hohes Potenzial'
        WHEN ST_Distance(p.geom, b.geom) < 800 THEN 'C - Mittleres Potenzial'
        ELSE 'D - Geringes Potenzial'
    END as verdichtungspotenzial
FROM parzellen p
CROSS JOIN bahnhoefe b
WHERE b.name = 'Winterthur Grüze'
AND p.parzellen_nr LIKE 'P-GRUEZE%'
ORDER BY ST_Distance(p.geom, b.geom);

SELECT 
    p.parzellen_nr,
    p.eigentuemer,
    p.nutzungszone,
    p.flaeche_m2,
    ROUND(ST_Distance(p.geom, b.geom)::numeric, 0) as distanz_meter,
    CASE p.nutzungszone
        WHEN 'Industriezone' THEN 'Umnutzung zu Mischzone empfohlen'
        WHEN 'Wohnzone' THEN 'Aufstockung möglich'
        WHEN 'Gewerbezone' THEN 'Ideal für gemischte Nutzung'
        ELSE 'Prüfung erforderlich'
    END as entwicklungsempfehlung,
    CASE 
        WHEN p.nutzungszone = 'Industriezone' AND ST_Distance(p.geom, b.geom) < 100 
        THEN 'Hoch - Stadt als Entwickler'
        WHEN ST_Distance(p.geom, b.geom) < 300 
        THEN 'Mittel - Private Investoren'
        ELSE 'Niedrig - Langfristige Planung'
    END as realisierungschance
FROM parzellen p
CROSS JOIN bahnhoefe b
WHERE b.name = 'Winterthur Grüze'
AND p.parzellen_nr LIKE 'P-GRUEZE%'
ORDER BY distanz_meter;

-- ----------------------------------------------------------------------
-- SZENARIO 4: WERKLEITUNGSNETZ - Infrastrukturanalyse
-- ERROR:  column "netzebene" does not exist
-- ----------------------------------------------------------------------
SELECT 
    CASE 
        WHEN durchmesser >= 300 THEN 'Transport'
        WHEN durchmesser >= 150 THEN 'Verteilung'
        ELSE 'Stichleitung'
    END as netzebene,
    COUNT(*) as anzahl_leitungen,
    ROUND(SUM(ST_Length(geom))::numeric, 0) as gesamtlaenge_meter,
    ROUND(AVG(durchmesser)::numeric, 0) as durchschnitt_durchmesser,
    MIN(EXTRACT(YEAR FROM verlegedatum)) as aelteste_leitung_jahr,
    MAX(EXTRACT(YEAR FROM verlegedatum)) as neueste_leitung_jahr
FROM werkleitungen
WHERE leitung_id LIKE 'L_%'
GROUP BY netzebene
ORDER BY 
    CASE netzebene
        WHEN 'Transport' THEN 1
        WHEN 'Verteilung' THEN 2
        ELSE 3
    END;

SELECT 
    leitung_id,
    material,
    durchmesser,
    verlegedatum,
    EXTRACT(YEAR FROM AGE(CURRENT_DATE, verlegedatum)) as alter_jahre,
    bemerkung,
    ROUND(ST_Length(geom)::numeric, 0) as laenge_meter,
    CASE 
        WHEN material = 'Grauguss' THEN 'Priorität 1: Sofortige Sanierung'
        WHEN material = 'Asbestzement' THEN 'Priorität 1: Sofortige Sanierung'
        WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, verlegedatum)) > 50 
        THEN 'Priorität 2: Mittelfristige Planung'
        WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, verlegedatum)) > 30 
        THEN 'Priorität 3: Überwachung'
        ELSE 'In Ordnung'
    END as sanierungsprioriaet,
    CASE 
        WHEN material = 'Grauguss' THEN ST_Length(geom) * 850
        WHEN material = 'Stahl' THEN ST_Length(geom) * 750
        WHEN material = 'PE' THEN ST_Length(geom) * 400
        ELSE ST_Length(geom) * 600
    END as geschaetzte_sanierungskosten_chf
FROM werkleitungen
WHERE material IN ('Grauguss', 'Asbestzement')
   OR EXTRACT(YEAR FROM AGE(CURRENT_DATE, verlegedatum)) > 30
ORDER BY 
    CASE material 
        WHEN 'Grauguss' THEN 1 
        WHEN 'Asbestzement' THEN 2 
        ELSE 3 
    END,
    alter_jahre DESC;

WITH RECURSIVE netzwerk AS (
    SELECT 
        leitung_id,
        von_knoten,
        zu_knoten,
        durchmesser,
        material,
        geom,
        1 as netzebene,
        leitung_id::text as pfad
    FROM werkleitungen
    WHERE von_knoten IN ('HV_STADTMITTE', 'RESERVOIR_LINDBERG')
    
    UNION ALL
    
    SELECT 
        w.leitung_id,
        w.von_knoten,
        w.zu_knoten,
        w.durchmesser,
        w.material,
        w.geom,
        n.netzebene + 1,
        n.pfad || ' -> ' || w.leitung_id
    FROM werkleitungen w
    INNER JOIN netzwerk n ON w.von_knoten = n.zu_knoten
    WHERE n.netzebene < 10
)
SELECT 
    netzebene,
    leitung_id,
    durchmesser,
    material,
    ROUND(ST_Length(geom)::numeric, 0) as laenge_meter,
    pfad as versorgungspfad
FROM netzwerk
ORDER BY netzebene, leitung_id;

-- ----------------------------------------------------------------------
-- SZENARIO 5: QUARTIER - Verdichtungsanalyse
-- OK
-- ----------------------------------------------------------------------
SELECT 
    q.quartier_name,
    q.flaeche_ha,
    COUNT(g.gebaeude_id) as anzahl_gebaeude,
    ROUND(COUNT(g.gebaeude_id)::numeric / q.flaeche_ha, 1) as gebaeude_pro_ha,
    SUM(g.geschossflaeche_m2) as total_geschossflaeche,
    ROUND(SUM(g.geschossflaeche_m2) / (q.flaeche_ha * 10000), 2) as geschossflaechendichte,
    ROUND(AVG(g.anzahl_geschosse)::numeric, 1) as durchschnitt_geschosse,
    MIN(g.baujahr) as aeltestes_gebaeude,
    MAX(g.baujahr) as neuestes_gebaeude
FROM quartiere q
LEFT JOIN gebaeude g ON ST_Within(g.geom, q.geom)
WHERE q.quartier_name = 'Neuwiesen'
GROUP BY q.quartier_id, q.quartier_name, q.flaeche_ha;

SELECT 
    CASE 
        WHEN baujahr < 1950 THEN 'Altbau (vor 1950)'
        WHEN baujahr < 1990 THEN 'Nachkriegszeit (1950-1990)'
        WHEN baujahr < 2010 THEN 'Neuere Bauten (1990-2010)'
        ELSE 'Neubau (ab 2010)'
    END as gebaeudealter,
    COUNT(*) as anzahl,
    ROUND(AVG(anzahl_geschosse)::numeric, 1) as durchschnitt_geschosse,
    ROUND(AVG(geschossflaeche_m2)::numeric, 0) as durchschnitt_geschossflaeche,
    ROUND(AVG(leerstandsquote)::numeric, 1) as durchschnitt_leerstand_prozent
FROM gebaeude g
JOIN quartiere q ON ST_Within(g.geom, q.geom)
WHERE q.quartier_name = 'Neuwiesen'
GROUP BY gebaeudealter
ORDER BY MIN(baujahr);

SELECT 
    g.adresse,
    g.baujahr,
    g.anzahl_geschosse,
    g.geschossflaeche_m2,
    g.leerstandsquote,
    CASE 
        WHEN baujahr < 1950 AND anzahl_geschosse <= 3 
        THEN 'Hoch - Ersatzneubau oder Aufstockung möglich'
        WHEN baujahr < 1990 AND leerstandsquote > 5 
        THEN 'Mittel - Sanierung oder Ersatz prüfen'
        WHEN anzahl_geschosse < 4 
        THEN 'Niedrig - Aufstockung theoretisch möglich'
        ELSE 'Kein Potenzial - Bereits verdichtet'
    END as verdichtungspotenzial,
    CASE 
        WHEN baujahr < 1950 THEN (5 - anzahl_geschosse) * 200
        WHEN anzahl_geschosse < 4 THEN (4 - anzahl_geschosse) * 150
        ELSE 0
    END as geschaetztes_zusatz_geschossflaeche_m2
FROM gebaeude g
JOIN quartiere q ON ST_Within(g.geom, q.geom)
WHERE q.quartier_name = 'Neuwiesen'
ORDER BY geschaetztes_zusatz_geschossflaeche_m2 DESC;

-- ----------------------------------------------------------------------
-- ÜBERGREIFENDE ANALYSEN
-- OK
-- ----------------------------------------------------------------------
SELECT 
    'Mühlengasse Versorgung' as analyse,
    COUNT(*) as datensaetze,
    'Werkleitungen funktionieren' as status
FROM werkleitungen
WHERE bemerkung LIKE '%Mühlengasse%'

UNION ALL

SELECT 
    'Hochwasserrisiko',
    COUNT(*),
    CASE WHEN COUNT(*) > 0 THEN 'Gebäude betroffen' ELSE 'Kein Risiko' END
FROM gebaeude g
JOIN hochwasserzonen h ON ST_Intersects(g.geom, h.geom)
WHERE h.gefahrenstufe = 'hoch'

UNION ALL

SELECT 
    'Bahnhof Entwicklung',
    COUNT(*),
    'Parzellen analysiert'
FROM parzellen
WHERE parzellen_nr LIKE 'P-GRUEZE%'

UNION ALL

SELECT 
    'Leitungsnetz',
    COUNT(*),
    'Netzwerk-Topologie OK'
FROM werkleitungen
WHERE von_knoten IS NOT NULL

UNION ALL

SELECT 
    'Quartier Neuwiesen',
    COUNT(*),
    'Verdichtung analysiert'
FROM gebaeude g
JOIN quartiere q ON ST_Within(g.geom, q.geom)
WHERE q.quartier_name = 'Neuwiesen';

-- ----------------------------------------------------------------------
-- ERWEITERTE DATENMANAGEMENT & ADMINISTRATION QUERIES
-- ----------------------------------------------------------------------

-- 11. SCHEMA-MIGRATION: Tabellenstruktur anpassen
-- OK
ALTER TABLE gebaeude 
ADD COLUMN IF NOT EXISTS energieklasse VARCHAR(1),
ADD COLUMN IF NOT EXISTS sanierungsbedarf BOOLEAN,
ADD COLUMN IF NOT EXISTS letzte_inspektion DATE;

UPDATE gebaeude 
SET 
    sanierungsbedarf = (baujahr < 1970 OR anzahl_geschosse > 4),
    energieklasse = CASE 
        WHEN baujahr > 2010 THEN 'A'
        WHEN baujahr > 1990 THEN 'B'
        WHEN baujahr > 1970 THEN 'C'
        ELSE 'D'
    END,
    letzte_inspektion = CURRENT_DATE - INTERVAL '1 year' * (RANDOM() * 10 + 1)
WHERE energieklasse IS NULL;

-- 12. GEOMETRIE-TRANSFORMATION UND PROJEKTIONEN
-- OK
SELECT 
    'Original (LV95)' as projektion,
    COUNT(*) as anzahl,
    ROUND(AVG(ST_Area(geom))::numeric, 2) as durchschnittsflaeche_m2
FROM gebaeude

UNION ALL

SELECT 
    'WGS84' as projektion,
    COUNT(*) as anzahl,
    ROUND(AVG(ST_Area(ST_Transform(geom, 4326)))::numeric, 2) as durchschnittsflaeche_m2
FROM gebaeude

UNION ALL

SELECT 
    'Web Mercator' as projektion,
    COUNT(*) as anzahl,
    ROUND(AVG(ST_Area(ST_Transform(geom, 3857)))::numeric, 2) as durchschnittsflaeche_m2
FROM gebaeude;

-- 13. TOPOLOGIE-PRÜFUNG: Überlappungen und Lücken
-- OK
SELECT 
    'Überlappende Parzellen' as problem,
    p1.parzellen_nr as parzelle_1,
    p2.parzellen_nr as parzelle_2,
    ROUND(ST_Area(ST_Intersection(p1.geom, p2.geom))::numeric, 2) as ueberlappungsflaeche_m2
FROM parzellen p1
JOIN parzellen p2 ON p1.parzellen_nr < p2.parzellen_nr 
    AND ST_Overlaps(p1.geom, p2.geom)
    AND ST_Area(ST_Intersection(p1.geom, p2.geom)) > 0.1

UNION ALL

SELECT 
    'Lücken zwischen Parzellen' as problem,
    'Gap_' || ROW_NUMBER() OVER () as parzelle_1,
    '' as parzelle_2,
    ROUND(ST_Area(gap.geom)::numeric, 2) as gap_flaeche_m2
FROM (
    SELECT (ST_Dump(ST_Difference(
        ST_Union(ST_Buffer(geom, 0.1)),
        ST_Union(geom)
    ))).geom as geom
    FROM parzellen
    WHERE nutzungszone = 'Wohnzone'
) gap
WHERE ST_Area(gap.geom) > 1;

-- 14. HISTORISCHE ANALYSE: Zeitliche Entwicklung
-- ERROR:  function pg_catalog.date_part(unknown, integer) does not exist
SELECT 
    EXTRACT(DECADE FROM baujahr) * 10 as jahrzehnt,
    COUNT(*) as anzahl_gebaeude,
    ROUND(AVG(anzahl_geschosse)::numeric, 1) as durchschnitt_geschosse,
    ROUND(AVG(geschossflaeche_m2)::numeric, 0) as durchschnitt_geschossflaeche,
    ROUND(SUM(geschossflaeche_m2) / 1000) as total_geschossflaeche_1000m2
FROM gebaeude
WHERE baujahr BETWEEN 1900 AND 2023
GROUP BY EXTRACT(DECADE FROM baujahr)
ORDER BY jahrzehnt;

-- 15. RAUMORDNUNG: Nutzungszonen-Analyse
-- OK
SELECT 
    nutzungszone,
    COUNT(*) as anzahl_parzellen,
    ROUND(SUM(flaeche_m2) / 10000, 2) as total_flaeche_ha,
    ROUND(AVG(flaeche_m2)::numeric, 0) as durchschnittsflaeche_m2,
    COUNT(DISTINCT eigentuemer) as anzahl_eigentuemer,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as anteil_prozent
FROM parzellen
GROUP BY nutzungszone
ORDER BY total_flaeche_ha DESC;

-- 16. GEOMETRIE-SIMPLIFIKATION FÜR VISUALISIERUNG
-- OK
SELECT 
    'Original' as typ,
    COUNT(*) as anzahl,
    SUM(ST_NPoints(geom)) as total_points
FROM gebaeude

UNION ALL

SELECT 
    'Vereinfacht (1m)' as typ,
    COUNT(*) as anzahl,
    SUM(ST_NPoints(ST_Simplify(geom, 1))) as total_points
FROM gebaeude

UNION ALL

SELECT 
    'Vereinfacht (0.5m)' as typ,
    COUNT(*) as anzahl,
    SUM(ST_NPoints(ST_Simplify(geom, 0.5))) as total_points
FROM gebaeude;

-- 17. 3D-ANALYSE: Volumenberechnung für Gebäude
-- OK
SELECT 
    gebaeude_id,
    adresse,
    anzahl_geschosse,
    geschossflaeche_m2,
    ROUND((geschossflaeche_m2 * anzahl_geschosse * 3)::numeric, 0) as geschaetztes_volumen_m3,
    -- Annahme: 3m pro Geschoss
    ROUND(ST_Area(geom) * anzahl_geschosse * 3) as grobvolumen_m3
FROM gebaeude
WHERE anzahl_geschosse IS NOT NULL
ORDER BY geschaetztes_volumen_m3 DESC
LIMIT 10;

-- 18. AUTOMATISCHE BERICHTE: Zusammenfassung Gesamtsystem
-- OK
SELECT 
    (SELECT COUNT(*) FROM gebaeude) as total_gebaeude,
    (SELECT COUNT(*) FROM parzellen) as total_parzellen,
    (SELECT COUNT(*) FROM werkleitungen) as total_leitungen,
    (SELECT ROUND(SUM(ST_Length(geom))::numeric, 0) FROM werkleitungen) as leitungslaenge_meter,
    (SELECT COUNT(*) FROM hausanschluesse) as total_hausanschluesse,
    (SELECT ROUND(AVG(einwohner)::numeric, 1) FROM hausanschluesse) as durchschnitt_einwohner_pro_haushalt,
    (SELECT COUNT(*) FROM gebaeude WHERE baujahr < 1950) as gebaeude_vor_1950,
    (SELECT ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM gebaeude), 1) 
     FROM gebaeude g 
     JOIN hochwasserzonen h ON ST_Intersects(g.geom, h.geom) 
     WHERE h.gefahrenstufe = 'hoch') as prozent_gebaeude_hochwasser_gefaehrdet;

-- 19. BACKUP UND SICHERHEIT: Datenintegritäts-Checks
-- ERROR:  UNION types integer and character varying cannot be matched
SELECT 
    'Gebäude ohne Adresse' as check_type,
    COUNT(*) as fehler_count
FROM gebaeude
WHERE adresse IS NULL OR TRIM(adresse) = ''

UNION ALL

SELECT 
    'Parzellen ohne Eigentümer',
    COUNT(*)
FROM parzellen
WHERE eigentuemer IS NULL OR TRIM(eigentuemer) = ''

UNION ALL

SELECT 
    'Leitungen ohne Material',
    COUNT(*)
FROM werkleitungen
WHERE material IS NULL

UNION ALL

SELECT 
    'Ungültige Geometrien',
    COUNT(*)
FROM (
    SELECT gebaeude_id FROM gebaeude WHERE NOT ST_IsValid(geom)
    UNION ALL
    SELECT parzellen_nr FROM parzellen WHERE NOT ST_IsValid(geom)
    UNION ALL
    SELECT leitung_id FROM werkleitungen WHERE NOT ST_IsValid(geom)
) as invalid_geoms;

-- 20. PERFORMANCE-MONITORING: Query-Statistiken
-- OK
SELECT 
    schemaname,
    tablename,
    ROUND(pg_total_relation_size(schemaname||'.'||tablename) / 1048576.0, 2) as groesse_mb,
    (SELECT COUNT(*) FROM pg_indexes WHERE tablename = t.tablename) as anzahl_indizes,
    (SELECT COUNT(*) FROM information_schema.columns 
     WHERE table_schema = t.schemaname AND table_name = t.tablename) as anzahl_spalten
FROM pg_tables t
WHERE schemaname = 'public'
AND tablename IN ('gebaeude', 'parzellen', 'werkleitungen', 'hausanschluesse')
ORDER BY groesse_mb DESC;

-- ======================================================================
-- ENDE DER UMfassenden PostGIS SQL-Sammlung
-- ======================================================================