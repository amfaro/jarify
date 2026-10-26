SELECT
   np.a
  ,n.b
FROM uni.nomination_points np -- staging nomination_points tables use corresponding points tables already
INNER JOIN _nominations     n USING (nomination_id)
LEFT JOIN common.clients    c ON c.client_id = n.client_id -- client names
;
