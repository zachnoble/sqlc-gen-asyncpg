-- name: InsertAllTypes :one
INSERT INTO all_types (i2, i2_null, i2_arr, i4, i4_null, i4_arr, i8, i8_null, i8_arr, f4, f4_null, f4_arr, f8, f8_null, f8_arr, num, num_null, num_arr, num_p, num_p_null, num_p_arr, money_, money__null, money__arr, b, b_null, b_arr, t, t_null, t_arr, vc, vc_null, vc_arr, ch, ch_null, ch_arr, ci, ci_null, ci_arr, nm, nm_null, nm_arr, by, by_null, by_arr, d, d_null, d_arr, tm, tm_null, tm_arr, tmtz, tmtz_null, tmtz_arr, ts, ts_null, ts_arr, tstz, tstz_null, tstz_arr, iv, iv_null, iv_arr, u, u_null, u_arr, inet_, inet__null, inet__arr, cidr_, cidr__null, cidr__arr, mac, mac_null, mac_arr, mac8, mac8_null, mac8_arr, js, js_null, js_arr, jsb, jsb_null, jsb_arr, jp, jp_null, jp_arr, x, x_null, x_arr, tsv, tsv_null, tsv_arr, tsq, tsq_null, tsq_arr, bt, bt_null, bt_arr, vb, vb_null, vb_arr, r4, r4_null, r4_arr, r8, r8_null, r8_arr, rn, rn_null, rn_arr, rd, rd_null, rd_arr, rts, rts_null, rts_arr, rtstz, rtstz_null, rtstz_arr, m4, m4_null, m4_arr, m8, m8_null, m8_arr, mn, mn_null, mn_arr, md, md_null, md_arr, mts, mts_null, mts_arr, mtstz, mtstz_null, mtstz_arr, pt, pt_null, pt_arr, ln, ln_null, ln_arr, ls, ls_null, ls_arr, bx, bx_null, bx_arr, pth, pth_null, pth_arr, pg, pg_null, pg_arr, cr, cr_null, cr_arr, o, o_null, o_arr, hs, hs_null, hs_arr, lt, lt_null, lt_arr, en, en_null, en_arr, dom, dom_null, comp, comp_null, comp_arr)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43, $44, $45, $46, $47, $48, $49, $50, $51, $52, $53, $54, $55, $56, $57, $58, $59, $60, $61, $62, $63, $64, $65, $66, $67, $68, $69, $70, $71, $72, $73, $74, $75, $76, $77, $78, $79, $80, $81, $82, $83, $84, $85, $86, $87, $88, $89, $90, $91, $92, $93, $94, $95, $96, $97, $98, $99, $100, $101, $102, $103, $104, $105, $106, $107, $108, $109, $110, $111, $112, $113, $114, $115, $116, $117, $118, $119, $120, $121, $122, $123, $124, $125, $126, $127, $128, $129, $130, $131, $132, $133, $134, $135, $136, $137, $138, $139, $140, $141, $142, $143, $144, $145, $146, $147, $148, $149, $150, $151, $152, $153, $154, $155, $156, $157, $158, $159, $160, $161, $162, $163, $164, $165, $166, $167, $168, $169, $170, $171, $172, $173, $174, $175, $176)
RETURNING *;

-- name: GetAllTypes :one
SELECT * FROM all_types WHERE id = $1;

-- name: ListAllTypes :many
SELECT * FROM all_types ORDER BY id;

-- name: CopyAllTypes :copyfrom
INSERT INTO all_types (i2, i2_null, i2_arr, i4, i4_null, i4_arr, i8, i8_null, i8_arr, f4, f4_null, f4_arr, f8, f8_null, f8_arr, num, num_null, num_arr, num_p, num_p_null, num_p_arr, money_, money__null, money__arr, b, b_null, b_arr, t, t_null, t_arr, vc, vc_null, vc_arr, ch, ch_null, ch_arr, ci, ci_null, ci_arr, nm, nm_null, nm_arr, by, by_null, by_arr, d, d_null, d_arr, tm, tm_null, tm_arr, tmtz, tmtz_null, tmtz_arr, ts, ts_null, ts_arr, tstz, tstz_null, tstz_arr, iv, iv_null, iv_arr, u, u_null, u_arr, inet_, inet__null, inet__arr, cidr_, cidr__null, cidr__arr, mac, mac_null, mac_arr, mac8, mac8_null, mac8_arr, js, js_null, js_arr, jsb, jsb_null, jsb_arr, jp, jp_null, jp_arr, x, x_null, x_arr, tsv, tsv_null, tsv_arr, tsq, tsq_null, tsq_arr, bt, bt_null, bt_arr, vb, vb_null, vb_arr, r4, r4_null, r4_arr, r8, r8_null, r8_arr, rn, rn_null, rn_arr, rd, rd_null, rd_arr, rts, rts_null, rts_arr, rtstz, rtstz_null, rtstz_arr, m4, m4_null, m4_arr, m8, m8_null, m8_arr, mn, mn_null, mn_arr, md, md_null, md_arr, mts, mts_null, mts_arr, mtstz, mtstz_null, mtstz_arr, pt, pt_null, pt_arr, ln, ln_null, ln_arr, ls, ls_null, ls_arr, bx, bx_null, bx_arr, pth, pth_null, pth_arr, pg, pg_null, pg_arr, cr, cr_null, cr_arr, o, o_null, o_arr, hs, hs_null, hs_arr, lt, lt_null, lt_arr, en, en_null, en_arr, dom, dom_null, comp, comp_null, comp_arr) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43, $44, $45, $46, $47, $48, $49, $50, $51, $52, $53, $54, $55, $56, $57, $58, $59, $60, $61, $62, $63, $64, $65, $66, $67, $68, $69, $70, $71, $72, $73, $74, $75, $76, $77, $78, $79, $80, $81, $82, $83, $84, $85, $86, $87, $88, $89, $90, $91, $92, $93, $94, $95, $96, $97, $98, $99, $100, $101, $102, $103, $104, $105, $106, $107, $108, $109, $110, $111, $112, $113, $114, $115, $116, $117, $118, $119, $120, $121, $122, $123, $124, $125, $126, $127, $128, $129, $130, $131, $132, $133, $134, $135, $136, $137, $138, $139, $140, $141, $142, $143, $144, $145, $146, $147, $148, $149, $150, $151, $152, $153, $154, $155, $156, $157, $158, $159, $160, $161, $162, $163, $164, $165, $166, $167, $168, $169, $170, $171, $172, $173, $174, $175, $176);

-- name: EchoI2 :one
SELECT i2, i2_null FROM all_types WHERE i2 = $1 LIMIT 1;

-- name: EchoI4 :one
SELECT i4, i4_null FROM all_types WHERE i4 = $1 LIMIT 1;

-- name: EchoI8 :one
SELECT i8, i8_null FROM all_types WHERE i8 = $1 LIMIT 1;

-- name: EchoF4 :one
SELECT f4, f4_null FROM all_types WHERE f4 = $1 LIMIT 1;

-- name: EchoF8 :one
SELECT f8, f8_null FROM all_types WHERE f8 = $1 LIMIT 1;

-- name: EchoNum :one
SELECT num, num_null FROM all_types WHERE num = $1 LIMIT 1;

-- name: EchoNump :one
SELECT num_p, num_p_null FROM all_types WHERE num_p = $1 LIMIT 1;

-- name: EchoMoney :one
SELECT money_, money__null FROM all_types WHERE id = $1;

-- name: EchoB :one
SELECT b, b_null FROM all_types WHERE b = $1 LIMIT 1;

-- name: EchoT :one
SELECT t, t_null FROM all_types WHERE t = $1 LIMIT 1;

-- name: EchoVc :one
SELECT vc, vc_null FROM all_types WHERE vc = $1 LIMIT 1;

-- name: EchoCh :one
SELECT ch, ch_null FROM all_types WHERE ch = $1 LIMIT 1;

-- name: EchoCi :one
SELECT ci, ci_null FROM all_types WHERE ci = $1 LIMIT 1;

-- name: EchoNm :one
SELECT nm, nm_null FROM all_types WHERE nm = $1 LIMIT 1;

-- name: EchoBy :one
SELECT by, by_null FROM all_types WHERE by = $1 LIMIT 1;

-- name: EchoD :one
SELECT d, d_null FROM all_types WHERE d = $1 LIMIT 1;

-- name: EchoTm :one
SELECT tm, tm_null FROM all_types WHERE tm = $1 LIMIT 1;

-- name: EchoTmtz :one
SELECT tmtz, tmtz_null FROM all_types WHERE tmtz = $1 LIMIT 1;

-- name: EchoTs :one
SELECT ts, ts_null FROM all_types WHERE ts = $1 LIMIT 1;

-- name: EchoTstz :one
SELECT tstz, tstz_null FROM all_types WHERE tstz = $1 LIMIT 1;

-- name: EchoIv :one
SELECT iv, iv_null FROM all_types WHERE iv = $1 LIMIT 1;

-- name: EchoU :one
SELECT u, u_null FROM all_types WHERE u = $1 LIMIT 1;

-- name: EchoInet :one
SELECT inet_, inet__null FROM all_types WHERE inet_ = $1 LIMIT 1;

-- name: EchoCidr :one
SELECT cidr_, cidr__null FROM all_types WHERE cidr_ = $1 LIMIT 1;

-- name: EchoMac :one
SELECT mac, mac_null FROM all_types WHERE mac = $1 LIMIT 1;

-- name: EchoMac8 :one
SELECT mac8, mac8_null FROM all_types WHERE mac8 = $1 LIMIT 1;

-- name: EchoJs :one
SELECT js, js_null FROM all_types WHERE id = $1;

-- name: EchoJsb :one
SELECT jsb, jsb_null FROM all_types WHERE jsb = $1 LIMIT 1;

-- name: EchoJp :one
SELECT jp, jp_null FROM all_types WHERE id = $1;

-- name: EchoX :one
SELECT x, x_null FROM all_types WHERE id = $1;

-- name: EchoTsv :one
SELECT tsv, tsv_null FROM all_types WHERE tsv = $1 LIMIT 1;

-- name: EchoTsq :one
SELECT tsq, tsq_null FROM all_types WHERE tsq = $1 LIMIT 1;

-- name: EchoBt :one
SELECT bt, bt_null FROM all_types WHERE bt = $1 LIMIT 1;

-- name: EchoVb :one
SELECT vb, vb_null FROM all_types WHERE vb = $1 LIMIT 1;

-- name: EchoR4 :one
SELECT r4, r4_null FROM all_types WHERE r4 = $1 LIMIT 1;

-- name: EchoR8 :one
SELECT r8, r8_null FROM all_types WHERE r8 = $1 LIMIT 1;

-- name: EchoRn :one
SELECT rn, rn_null FROM all_types WHERE rn = $1 LIMIT 1;

-- name: EchoRd :one
SELECT rd, rd_null FROM all_types WHERE rd = $1 LIMIT 1;

-- name: EchoRts :one
SELECT rts, rts_null FROM all_types WHERE rts = $1 LIMIT 1;

-- name: EchoRtstz :one
SELECT rtstz, rtstz_null FROM all_types WHERE rtstz = $1 LIMIT 1;

-- name: EchoM4 :one
SELECT m4, m4_null FROM all_types WHERE m4 = $1 LIMIT 1;

-- name: EchoM8 :one
SELECT m8, m8_null FROM all_types WHERE m8 = $1 LIMIT 1;

-- name: EchoMn :one
SELECT mn, mn_null FROM all_types WHERE mn = $1 LIMIT 1;

-- name: EchoMd :one
SELECT md, md_null FROM all_types WHERE md = $1 LIMIT 1;

-- name: EchoMts :one
SELECT mts, mts_null FROM all_types WHERE mts = $1 LIMIT 1;

-- name: EchoMtstz :one
SELECT mtstz, mtstz_null FROM all_types WHERE mtstz = $1 LIMIT 1;

-- name: EchoPt :one
SELECT pt, pt_null FROM all_types WHERE id = $1;

-- name: EchoLn :one
SELECT ln, ln_null FROM all_types WHERE id = $1;

-- name: EchoLs :one
SELECT ls, ls_null FROM all_types WHERE id = $1;

-- name: EchoBx :one
SELECT bx, bx_null FROM all_types WHERE id = $1;

-- name: EchoPth :one
SELECT pth, pth_null FROM all_types WHERE id = $1;

-- name: EchoPg :one
SELECT pg, pg_null FROM all_types WHERE id = $1;

-- name: EchoCr :one
SELECT cr, cr_null FROM all_types WHERE id = $1;

-- name: EchoO :one
SELECT o, o_null FROM all_types WHERE o = $1 LIMIT 1;

-- name: EchoHs :one
SELECT hs, hs_null FROM all_types WHERE hs = $1 LIMIT 1;

-- name: EchoLt :one
SELECT lt, lt_null FROM all_types WHERE lt = $1 LIMIT 1;

-- name: EchoEn :one
SELECT en, en_null FROM all_types WHERE en = $1 LIMIT 1;

-- name: EchoDom :one
SELECT dom, dom_null FROM all_types WHERE dom = $1 LIMIT 1;

-- name: EchoComp :one
SELECT comp, comp_null FROM all_types WHERE id = $1;

-- name: InsertMultiDim :one
INSERT INTO multi_dim (grid, cube, moods) VALUES ($1, $2, $3) RETURNING *;

-- name: ScalarCasts :one
SELECT $1::int AS i, $2::text[] AS arr, $3::mood AS mood, $4::mood[] AS moods, $5::uuid AS u;

-- name: NullLiterals :one
SELECT NULL::int AS ni, NULL::mood AS nm, NULL::mood[] AS nma, NULL::text[] AS nta;

-- name: MoodArrayNullElems :one
SELECT ARRAY['ok', NULL]::mood[] AS moods;

-- name: MultirangeArray :one
SELECT ARRAY['{[1,3)}', '{}', '{[5,6),[8,9)}']::int4multirange[] AS m;

-- name: GeometryArrays :one
SELECT ARRAY['[(0,0),(1,1)]'::path, NULL]::path[] AS paths, ARRAY['((0,0),(1,1),(1,0))'::polygon] AS polys;

-- name: InsertEmbedding :one
INSERT INTO embeddings (v, v_null, v_arr) VALUES ($1, $2, $3) RETURNING *;

-- name: NearestEmbedding :one
SELECT id, v <-> $1 AS dist FROM embeddings ORDER BY v <-> $1 LIMIT 1;

-- name: CopyEmbeddings :copyfrom
INSERT INTO embeddings (v, v_null) VALUES ($1, $2);

-- name: ListEmbeddings :many
SELECT * FROM embeddings ORDER BY id;
