
-- ajout du code commune sur geo_label

-- ajout par intersection et jointure
BEGIN;

UPDATE [PREFIXE]geo_label SET geo_commune = t.commune FROM (SELECT label.*, comm.commune FROM [PREFIXE]geo_commune comm, [PREFIXE]geo_label label WHERE ST_Intersects(comm.geom, label.geom)) AS t WHERE t.object_rid = geo_label.object_rid;

COMMIT;