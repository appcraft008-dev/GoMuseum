-- 文本台账统计(docs/ops/text-followups.md 的数据源)。只读。
-- 跑法(prod):
--   scp docs/ops/text-inventory.sql root@VPS:/tmp/ && \
--   docker exec -i gomuseum_prod_postgres psql -U gomuseum -d gomuseum -t -A -F' | ' < /tmp/text-inventory.sql
-- 口径:只算 status='published' 且 body 非空;以 en 为轴心(补语种从 en 翻译)。

-- ① 全视图:每馆 × 语言 × 类型 的已发布数
--   guide=标准导览(件数) / deep=深度段(段数,guide 以外的段) / qa=有问答的件数 / bio=有简介的作者数
WITH langs(lang) AS (VALUES ('en'),('fr'),('de'),('es'),('it'),('zh'),('pl'),('ja'),('ko'),('zh-hant')),
po AS (SELECT mo.id, m.slug, mo.attributes->>'artist_qid' aqid
       FROM museum_objects mo JOIN museums m ON m.id = mo.museum_id),
sec AS (SELECT po.slug, s.object_id, s.language, s.section_code
        FROM object_content_sections s JOIN po ON po.id = s.object_id
        WHERE s.status = 'published' AND s.body IS NOT NULL),
en_objs AS (SELECT DISTINCT slug, object_id FROM sec WHERE language = 'en'),
arts AS (SELECT DISTINCT e.slug, a.qid, a.bio
         FROM en_objs e JOIN po ON po.id = e.object_id JOIN artists a ON a.qid = po.aqid)
SELECT 'VIEW', slug, 'guide', language, count(DISTINCT object_id)::text FROM sec WHERE section_code = 'guide' GROUP BY 2, 4
UNION ALL
SELECT 'VIEW', slug, 'deep', language, count(*)::text FROM sec WHERE section_code <> 'guide' GROUP BY 2, 4
UNION ALL
SELECT 'VIEW', po.slug, 'qa', q.language, count(DISTINCT q.object_id)::text
FROM object_suggested_questions q JOIN po ON po.id = q.object_id WHERE q.status = 'published' GROUP BY 2, 4
UNION ALL
SELECT 'VIEW', a.slug, 'bio', l.lang, count(*)::text
FROM arts a CROSS JOIN langs l WHERE coalesce(a.bio->>l.lang, '') <> '' GROUP BY 2, 4
ORDER BY 2, 3, 4;

-- ② 缺口明细:有已发布 en 但该语言没有已发布对应物的条目;第 6 列 = 该语言现有行的状态
WITH langs(lang) AS (VALUES ('fr'),('de'),('es'),('it'),('zh'),('pl'),('ja'),('ko'),('zh-hant')),
po AS (SELECT mo.id, mo.qid, m.slug, mo.attributes->>'artist_qid' aqid
       FROM museum_objects mo JOIN museums m ON m.id = mo.museum_id),
en_sec AS (SELECT s.object_id, s.section_code, po.slug, po.qid
           FROM object_content_sections s JOIN po ON po.id = s.object_id
           WHERE s.language = 'en' AND s.status = 'published' AND s.body IS NOT NULL)
SELECT 'GAP_SEC', e.slug, e.qid, e.section_code, l.lang, coalesce(t.status, '(无行)')
FROM en_sec e CROSS JOIN langs l
LEFT JOIN object_content_sections t
  ON t.object_id = e.object_id AND t.section_code = e.section_code AND t.language = l.lang
WHERE t.id IS NULL OR t.status <> 'published' OR t.body IS NULL
UNION ALL
SELECT 'GAP_QA', po.slug, po.qid,
       CASE WHEN EXISTS (SELECT 1 FROM en_sec e WHERE e.object_id = po.id) THEN '' ELSE 'en段未发布' END,
       l.lang,
       coalesce((SELECT string_agg(DISTINCT x.status, ',') FROM object_suggested_questions x
                 WHERE x.object_id = po.id AND x.language = l.lang), '(无行)')
FROM po CROSS JOIN langs l
WHERE EXISTS (SELECT 1 FROM object_suggested_questions q
              WHERE q.object_id = po.id AND q.language = 'en' AND q.status = 'published')
  AND NOT EXISTS (SELECT 1 FROM object_suggested_questions q
                  WHERE q.object_id = po.id AND q.language = l.lang AND q.status = 'published')
UNION ALL
SELECT 'GAP_BIO', '', a.qid, coalesce(a.name_en, ''), l.lang, ''
FROM (SELECT DISTINCT a.qid, a.name_en, a.bio FROM artists a JOIN po ON po.aqid = a.qid
      WHERE po.id IN (SELECT object_id FROM en_sec) AND coalesce(a.bio->>'en', '') <> '') a
CROSS JOIN langs l WHERE coalesce(a.bio->>l.lang, '') = ''
ORDER BY 1, 2, 3, 5;
