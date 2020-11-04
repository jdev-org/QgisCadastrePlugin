
-- ajout du code commune sur geo_label

-- création d'un nouvel attribut
ALTER TABLE label_all_brest.geo_label ADD COLUMN IF NOT EXISTS geo_commune text;

-- ajout par intersection et jointure
BEGIN;

UPDATE label_all_brest.geo_label SET geo_commune = t.commune
FROM (
	SELECT label.*, comm.commune
	FROM label_all_brest.geo_commune comm, label_all_brest.geo_label label
	WHERE ST_Intersects(comm.geom, label.geom)
) AS t
WHERE t.object_rid = geo_label.object_rid;

COMMIT;