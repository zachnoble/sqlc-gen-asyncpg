package gen

import (
	"context"
	"fmt"
	"sort"
	"strings"

	"github.com/sqlc-dev/plugin-sdk-go/plugin"
)

const Version = "v0.1.0"

func Generate(_ context.Context, req *plugin.GenerateRequest) (*plugin.GenerateResponse, error) {
	opts, err := parseOptions(req)
	if err != nil {
		return nil, err
	}
	g := &generator{req: req, opts: opts, defaultSchema: "public"}
	if req.Catalog != nil && req.Catalog.DefaultSchema != "" {
		g.defaultSchema = req.Catalog.DefaultSchema
	}
	if req.Catalog == nil {
		req.Catalog = &plugin.Catalog{}
	}
	g.buildEnums()
	g.buildModels()
	if err := g.buildQueries(); err != nil {
		return nil, err
	}
	g.markUsed()
	if err := g.validate(); err != nil {
		return nil, err
	}
	files, err := g.render()
	if err != nil {
		return nil, err
	}
	resp := &plugin.GenerateResponse{}
	names := make([]string, 0, len(files))
	for n := range files {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		resp.Files = append(resp.Files, &plugin.File{Name: n, Contents: []byte(files[n])})
	}
	return resp, nil
}

func fileModule(opt, def string) string {
	if opt == "" {
		return def
	}
	return strings.TrimSuffix(opt, ".py")
}

type layout struct {
	models, db, querier, batch, copyfrom string
	queryModules                         []string // sorted
	queryMixin                           map[string]string
}

func (g *generator) layout() (*layout, error) {
	l := &layout{
		models:     fileModule(g.opts.OutputModelsFileName, "models"),
		db:         fileModule(g.opts.OutputDBFileName, "db"),
		querier:    fileModule(g.opts.OutputQuerierFileName, "querier"),
		batch:      fileModule(g.opts.OutputBatchFileName, "batch"),
		copyfrom:   fileModule(g.opts.OutputCopyfromFileName, "copyfrom"),
		queryMixin: map[string]string{},
	}
	reserved := map[string]string{
		"__init__": "the package __init__",
		l.models:   "the models module",
		l.db:       "the db module",
	}
	if g.opts.EmitInterface {
		if _, ok := reserved[l.querier]; ok {
			return nil, fmt.Errorf("output file name %s.py is used twice", l.querier)
		}
		reserved[l.querier] = "the querier module"
	}
	if g.usesBatch() {
		if _, ok := reserved[l.batch]; ok {
			return nil, fmt.Errorf("output file name %s.py is used twice", l.batch)
		}
		reserved[l.batch] = "the batch module"
	}
	if g.usesCopyFrom() {
		if _, ok := reserved[l.copyfrom]; ok {
			return nil, fmt.Errorf("output file name %s.py is used twice", l.copyfrom)
		}
		reserved[l.copyfrom] = "the copyfrom module"
	}
	if l.models == l.db {
		return nil, fmt.Errorf("output file name %s.py is used twice", l.db)
	}
	sources := map[string]string{}
	for _, q := range g.queries {
		mod := sanitize(moduleForSource(q.Source) + strings.TrimSuffix(g.opts.OutputFilesSuffix, ".py"))
		if prev, ok := sources[mod]; ok && prev != q.Source {
			return nil, fmt.Errorf("query files %s and %s both map to the Python module %s.py", prev, q.Source, mod)
		}
		if what, ok := reserved[mod]; ok {
			return nil, fmt.Errorf("query file %s maps to %s.py which collides with %s; rename the file or set output_files_suffix / output_*_file_name", q.Source, mod, what)
		}
		sources[mod] = q.Source
		q.Module = mod
	}
	mixins := map[string]string{}
	for mod, src := range sources {
		l.queryModules = append(l.queryModules, mod)
		name := g.pascal(mod) + "Queries"
		if prev, ok := mixins[name]; ok {
			return nil, fmt.Errorf("query files %s and %s both map to the class %s", prev, src, name)
		}
		if name == "Queries" || name == "DBTX" {
			name = "Queries" + name
		}
		mixins[name] = src
		l.queryMixin[mod] = name
	}
	sort.Strings(l.queryModules)
	return l, nil
}

func (g *generator) pascal(name string) string {
	saved := g.opts.Rename
	g.opts.Rename = nil
	defer func() { g.opts.Rename = saved }()
	return g.className(name)
}

func (g *generator) usesBatch() bool {
	for _, q := range g.queries {
		if q.isBatch() {
			return true
		}
	}
	return false
}

func (g *generator) usesCopyFrom() bool {
	for _, q := range g.queries {
		if q.Cmd == ":copyfrom" {
			return true
		}
	}
	return false
}

func (g *generator) render() (map[string]string, error) {
	l, err := g.layout()
	if err != nil {
		return nil, err
	}
	g.lay = l
	files := map[string]string{}
	files["__init__.py"] = g.newModule("__init__", "").render()
	files[l.models+".py"] = g.renderModels(l)
	for _, mod := range l.queryModules {
		files[mod+".py"] = g.renderQueryModule(l, mod)
	}
	if g.usesBatch() {
		files[l.batch+".py"] = g.renderBatch(l)
	}
	if g.usesCopyFrom() {
		files[l.copyfrom+".py"] = g.renderCopyFrom(l)
	}
	files[l.db+".py"] = g.renderDB(l)
	if g.opts.EmitInterface {
		files[l.querier+".py"] = g.renderQuerier(l)
	}
	return files, nil
}

func (g *generator) structKwargs() string {
	keys := make([]string, 0, len(g.opts.MsgspecStructOptions))
	for k := range g.opts.MsgspecStructOptions {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var parts []string
	for _, k := range keys {
		v, _ := pyLiteral(g.opts.MsgspecStructOptions[k])
		parts = append(parts, k+"="+v)
	}
	return strings.Join(parts, ", ")
}

func (m *pyModule) structDef(s *Struct) {
	m.addImport("msgspec")
	bases := m.expr("msgspec") + ".Struct"
	kw := m.g.structKwargs()
	if m.g.opts.EmitJSONTags {
		var pairs []string
		for _, f := range s.Fields {
			if f.JSONName != f.Name {
				pairs = append(pairs, pyStr(f.Name)+": "+pyStr(f.JSONName))
			}
		}
		if len(pairs) > 0 {
			r := "rename={" + strings.Join(pairs, ", ") + "}"
			if kw != "" {
				kw += ", " + r
			} else {
				kw = r
			}
		}
	}
	if kw != "" {
		bases += ", " + kw
	}
	m.line("")
	m.line("")
	m.line("class %s(%s):", s.Name, bases)
	m.in()
	var doc []string
	if s.Comment != "" {
		doc = strings.Split(s.Comment, "\n")
	}
	m.docstring(doc)
	if len(s.Fields) == 0 && len(doc) == 0 {
		m.line("pass")
	}
	for _, f := range s.Fields {
		if f.Comment != "" {
			for c := range strings.SplitSeq(f.Comment, "\n") {
				m.line("%s", "# "+strings.TrimRight(c, " \t"))
			}
		}
		m.line("%s: %s", f.Name, m.ann(f.Type))
	}
	m.out()
}

func (m *pyModule) registerStructScope(s *Struct) {
	for _, f := range s.Fields {
		m.classScope[f.Name] = true
	}
}

func (g *generator) renderModels(l *layout) string {
	m := g.newModule(l.models, "")
	m.isModels = true
	for _, s := range g.models {
		if s.used {
			m.registerStructScope(s)
		}
	}
	for _, e := range g.enums {
		if !e.used {
			continue
		}
		m.addImport("enum")
		for _, mem := range e.Members {
			m.classScope[mem.Name] = true
		}
	}
	for _, e := range g.enums {
		if !e.used {
			continue
		}
		m.line("")
		m.line("")
		m.line("class %s(%s.StrEnum):", e.Name, m.expr("enum"))
		m.in()
		if e.Comment != "" {
			m.docstring(strings.Split(e.Comment, "\n"))
		}
		if len(e.Members) == 0 && e.Comment == "" && !g.opts.EmitEnumValidMethod && !g.opts.EmitAllEnumValues {
			m.line("pass")
		}
		for _, mem := range e.Members {
			m.line("%s = %s", mem.Name, pyStr(mem.Value))
		}
		if g.opts.EmitEnumValidMethod {
			m.addImport("typing")
			m.line("")
			m.line("@classmethod")
			m.line("def valid(cls, value: %s) -> bool:", m.expr("typing")+".Any")
			m.in()
			m.line(`"""Report whether value is a member value."""`)
			m.line("return value in cls._value2member_map_")
			m.out()
		}
		if g.opts.EmitAllEnumValues {
			m.addImport("typing")
			m.line("")
			m.line("@classmethod")
			m.line("def all_values(cls) -> list[%s.Self]:", m.expr("typing"))
			m.in()
			m.line(`"""Return all members in declaration order."""`)
			m.line("return list(cls)")
			m.out()
		}
		m.out()
		if a, ok := m.aliasFor(e.Name); ok {
			m.line("")
			m.line("")
			m.line("%s = %s", a, e.Name)
		}
	}
	for _, s := range g.models {
		if !s.used {
			continue
		}
		m.structDef(s)
	}
	return m.render()
}

func (g *generator) dbArg() bool { return g.opts.EmitMethodsWithDBArgument }

func (g *generator) modelsModule() string {
	if g.lay != nil {
		return g.lay.models
	}
	return "models"
}

// methodCtx holds per-method naming.
type methodCtx struct {
	q      *Query
	params []string // python parameter names for ArgFields (individual modes)
	argVar string   // name of the struct / sequence parameter
	conn   string   // expression used to reach the connection
}

func (m *pyModule) newMethodCtx(q *Query) *methodCtx {
	reserved := map[string]bool{"self": true}
	for n := range localNames {
		reserved[n] = true
	}
	for n := range m.moduleNames {
		reserved[n] = true
	}
	reserved[m.g.modelsModule()] = true
	for _, n := range []string{"models", "typing", "asyncpg", "msgspec", "datetime", "decimal", "uuid", "ipaddress", "enum", "contextlib", "DBTX"} {
		reserved[n] = true
	}
	for a := range m.aliases {
		reserved[m.aliases[a]] = true
	}
	mc := &methodCtx{q: q, conn: "self._conn"}
	take := func(n string) string {
		for reserved[n] {
			n += "_"
		}
		reserved[n] = true
		return n
	}
	if m.g.dbArg() {
		mc.conn = take("conn")
	}
	switch q.ArgKind {
	case argSingle, argFields:
		for _, f := range q.ArgFields {
			mc.params = append(mc.params, take(f.Name))
		}
	case argStruct:
		mc.argVar = take("arg")
	}
	if q.isBatch() || q.Cmd == ":copyfrom" {
		mc.argVar = take("args")
		mc.params = nil
	}
	return mc
}

var localNames = map[string]bool{
	"_row": true, "_rows": true, "_r": true, "_x": true, "_status": true, "_n": true,
	"_sqlc_enum": true, "_sqlc_enum_array": true,
	"_e": true, "_stmt": true, "_a": true, "_out": true, "_c": true, "_tx": true, "_records": true,
}

// signature renders the parameter list (without self).
func (m *pyModule) signature(mc *methodCtx) string {
	var parts []string
	q := mc.q
	if m.g.dbArg() {
		parts = append(parts, mc.conn+": \"DBTX\"")
	}
	switch {
	case q.isBatch() || q.Cmd == ":copyfrom":
		m.addImport("collections.abc")
		parts = append(parts, fmt.Sprintf("%s: %s.Sequence[%s]", mc.argVar, m.expr("collections")+".abc", m.argElemType(q)))
	case q.ArgKind == argSingle || q.ArgKind == argFields:
		for i, f := range q.ArgFields {
			parts = append(parts, fmt.Sprintf("%s: %s", mc.params[i], m.ann(f.Type)))
		}
	case q.ArgKind == argStruct:
		parts = append(parts, fmt.Sprintf("%s: %s", mc.argVar, m.structRef(q.ArgStruct, q)))
	}
	return strings.Join(parts, ", ")
}

func (m *pyModule) argElemType(q *Query) string {
	if q.ArgKind == argSingle {
		return m.ann(q.ArgFields[0].Type)
	}
	return m.structRef(q.ArgStruct, q)
}

// structRef references a Params/Row struct from the current module.
func (m *pyModule) structRef(s *Struct, q *Query) string {
	if s.IsModel {
		return m.ann(fieldType{Elem: &pyType{Expr: "{models}" + s.Name}})
	}
	home := q.Module
	if q.isBatch() {
		home = m.g.lay.batch
	}
	if home == m.name {
		return s.Name
	}
	m.addFrom("."+home, s.Name)
	return s.Name
}

func (m *pyModule) retType(q *Query) string {
	switch q.RetKind {
	case retScalar:
		return m.ann(q.RetScalar)
	case retStruct:
		return m.structRef(q.RetStruct, q)
	}
	return "None"
}

// methodReturn renders the return annotation of the public method.
func (m *pyModule) methodReturn(q *Query) string {
	return m.annExpr(m.rawMethodReturn(q))
}

func (m *pyModule) rawMethodReturn(q *Query) string {
	switch q.Cmd {
	case ":one":
		r := m.retType(q)
		if q.RetKind == retScalar && (q.RetScalar.Nullable || r == "None") {
			return r
		}
		return r + " | None"
	case ":many":
		return "list[" + m.retType(q) + "]"
	case ":exec", ":batchexec":
		return "None"
	case ":execrows", ":copyfrom":
		return "int"
	case ":execresult":
		return "str"
	case ":batchone":
		r := m.retType(q)
		if q.RetKind == retScalar && (q.RetScalar.Nullable || r == "None") {
			return "list[" + r + "]"
		}
		return "list[" + r + " | None]"
	case ":batchmany":
		return "list[list[" + m.retType(q) + "]]"
	}
	return "None"
}

// argValues returns the python expressions passed to asyncpg for $1..$N.
func (m *pyModule) argValues(mc *methodCtx, item string) []string {
	q := mc.q
	var out []string
	for _, idx := range q.ArgOrder {
		switch {
		case q.isBatch() || q.Cmd == ":copyfrom":
			if q.ArgKind == argSingle {
				out = append(out, item)
			} else {
				out = append(out, item+"."+q.ArgStruct.Fields[idx].Name)
			}
		case q.ArgKind == argStruct:
			out = append(out, mc.argVar+"."+q.ArgStruct.Fields[idx].Name)
		default:
			out = append(out, mc.params[idx])
		}
	}
	return out
}

// convert renders the conversion of a raw asyncpg value. The bool reports an
// Any-typed result that needs a cast when returned.
func (m *pyModule) convert(expr string, t fieldType, nullSafe bool) (string, bool) {
	if !t.needsConversion() {
		return expr, true
	}
	enumRef := m.ann(fieldType{Elem: t.Elem})
	if t.Dims > 0 {
		// NULL elements pass through; element types stay non-optional, as in Go.
		m.needArrayHelper = true
		m.addImport("typing")
		m.expr("typing")
		return fmt.Sprintf("_sqlc_enum_array(%s, %s, %d)", enumRef, expr, t.Dims), true
	}
	if nullSafe && !t.Nullable {
		m.needEnumHelper = true
		m.addImport("typing")
		m.expr("typing")
		return fmt.Sprintf("_sqlc_enum(%s, %s)", enumRef, expr), true
	}
	if t.Nullable {
		return fmt.Sprintf("None if %s is None else %s(%s)", expr, enumRef, expr), false
	}
	return enumRef + "(" + expr + ")", false
}

// rowExpr converts record rec into the query's return value.
func (m *pyModule) rowExpr(q *Query, rec string) string {
	if q.RetKind == retScalar {
		e, _ := m.convert(rec+"[0]", q.RetScalar, false)
		return e
	}
	s := q.RetStruct
	idx := 0
	var build func(s *Struct, isRet bool) string
	build = func(s *Struct, isRet bool) string {
		var parts []string
		for _, f := range s.Fields {
			if f.Embed != nil {
				parts = append(parts, f.Name+"="+build(f.Embed, false))
				continue
			}
			// Embeds may be the NULL side of an outer join.
			conv, _ := m.convert(fmt.Sprintf("%s[%d]", rec, idx), f.Type, !isRet)
			parts = append(parts, f.Name+"="+conv)
			idx++
		}
		ctor := s.Name
		if s.IsModel {
			ctor = m.ann(fieldType{Elem: &pyType{Expr: "{models}" + s.Name}})
		} else if isRet {
			ctor = m.structRef(s, q)
		}
		if len(parts) == 0 {
			return ctor + "()"
		}
		return ctor + "(" + strings.Join(parts, ", ") + ")"
	}
	return build(s, true)
}

func callArgs(sqlConst string, args []string) string {
	if len(args) == 0 {
		return sqlConst
	}
	return sqlConst + ", " + strings.Join(args, ", ")
}

func (m *pyModule) methodHeader(mc *methodCtx) {
	q := mc.q
	sig := m.signature(mc)
	if sig != "" {
		sig = ", " + sig
	}
	m.line("")
	m.line("async def %s(self%s) -> %s:", q.Method, sig, m.methodReturn(q))
	m.in()
	m.docstring(q.Comments)
	if m.g.opts.WrapErrors {
		m.line("try:")
		m.in()
	}
}

func (m *pyModule) methodFooter(mc *methodCtx) {
	if m.g.opts.WrapErrors {
		m.out()
		m.line("except Exception as _e:")
		m.in()
		m.line("_e.add_note(%s)", pyStr("query "+mc.q.Name))
		m.line("raise")
		m.out()
	}
	m.out()
}

// call renders an awaited fetch/fetchrow/execute, using prepared statements
// when enabled.
func (m *pyModule) call(mc *methodCtx, kind, target, sqlConst string, args []string) {
	q := mc.q
	assign := target + " = "
	if target == "" {
		assign = ""
	}
	if !m.g.opts.EmitPreparedQueries {
		m.line("%sawait %s.%s(%s)", assign, mc.conn, kind, callArgs(sqlConst, args))
		return
	}
	_ = q
	m.line("_stmt = self._stmts.get(%s)", sqlConst)
	m.line("if _stmt is not None:")
	m.in()
	switch kind {
	case "execute":
		m.line("await _stmt.fetch(%s)", strings.Join(args, ", "))
		if target != "" {
			m.line("%s = %s.cast(str, _stmt.get_statusmsg())", target, m.expr("typing"))
		}
	default:
		m.line("%sawait _stmt.%s(%s)", assign, kind, strings.Join(args, ", "))
	}
	m.out()
	m.line("else:")
	m.in()
	m.line("%sawait %s.%s(%s)", assign, mc.conn, kind, callArgs(sqlConst, args))
	m.out()
}

func (m *pyModule) queryMethod(q *Query) {
	mc := m.newMethodCtx(q)
	m.methodHeader(mc)
	args := m.argValues(mc, "")
	c := m.expr(q.Const)
	switch q.Cmd {
	case ":one":
		m.call(mc, "fetchrow", "_row", c, args)
		m.line("if _row is None:")
		m.in()
		m.line("return None")
		m.out()
		if q.RetKind == retScalar {
			e, isAny := m.convert("_row[0]", q.RetScalar, false)
			if isAny && (!q.RetScalar.Elem.Unknown || q.RetScalar.Dims != 0) {
				m.addImport("typing")
				e = fmt.Sprintf("%s.cast(%s, %s)", m.expr("typing"), m.retType(q), e)
			}
			m.line("return %s", e)
		} else {
			m.line("return %s", m.rowExpr(q, "_row"))
		}
	case ":many":
		m.call(mc, "fetch", "_rows", c, args)
		m.line("return [%s for _r in _rows]", m.rowExpr(q, "_r"))
	case ":exec":
		m.call(mc, "execute", "", c, args)
	case ":execrows":
		m.call(mc, "execute", "_status", c, args)
		m.line(`_n = _status.rpartition(" ")[2]`)
		m.line("return int(_n) if _n.isdigit() else 0")
	case ":execresult":
		m.call(mc, "execute", "_status", c, args)
		m.line("return _status")
	}
	m.methodFooter(mc)
}

func (m *pyModule) sqlConst(q *Query) {
	m.moduleNames[q.Const] = true
	m.line("")
	if !q.hasMethod() {
		m.line("# :execlastid is unsupported on PostgreSQL; use RETURNING with :one.")
	}
	m.raw(q.Const + " = " + pyTripleStr(fmt.Sprintf("-- name: %s %s\n%s\n", q.Name, q.Cmd, q.SQL)))
}

func (m *pyModule) mixinPrelude(qs []*Query) {
	m.addImport("typing")
	m.line("__slots__ = ()")
	if m.g.opts.EmitPreparedQueries {
		var items []string
		for _, q := range qs {
			if q.Cmd == ":copyfrom" {
				continue
			}
			items = append(items, fmt.Sprintf("(%s, %s)", pyStr(q.Name), m.expr(q.Const)))
		}
		m.line("_sqlc_statements: %s.ClassVar[tuple[tuple[str, str], ...]] = (", m.expr("typing"))
		m.in()
		for _, it := range items {
			m.line("%s,", it)
		}
		m.out()
		m.line(")")
	}
	if !m.g.dbArg() {
		m.line("")
		m.line("if %s.TYPE_CHECKING:", m.expr("typing"))
		m.in()
		m.line(`_conn: "DBTX"`)
		if m.g.opts.EmitPreparedQueries {
			m.line("_stmts: dict[str, %s.Any]", m.expr("typing"))
		}
		m.out()
	}
	m.addTypeOnly("."+m.g.lay.db, "DBTX")
}

func (g *generator) renderQueryModule(l *layout, mod string) string {
	var qs []*Query
	source := ""
	for _, q := range g.queries {
		if q.Module == mod {
			qs = append(qs, q)
			source = q.Source
		}
	}
	m := g.newModule(mod, source)
	mixin := l.queryMixin[mod]
	m.moduleNames[mixin] = true
	for _, q := range qs {
		if q.isBatch() {
			continue
		}
		if q.EmitArg && q.ArgStruct != nil {
			m.registerStructScope(q.ArgStruct)
			m.moduleNames[q.ArgStruct.Name] = true
		}
		if q.EmitRet {
			m.registerStructScope(q.RetStruct)
			m.moduleNames[q.RetStruct.Name] = true
		}
		if q.Cmd != ":copyfrom" {
			m.classScope[q.Method] = true
			m.moduleNames[q.Const] = true
		}
	}
	for _, q := range qs {
		if q.isBatch() {
			continue
		}
		if q.Cmd != ":copyfrom" {
			m.sqlConst(q)
		}
		if q.EmitArg && q.ArgStruct != nil {
			m.structDef(q.ArgStruct)
		}
		if q.EmitRet {
			m.structDef(q.RetStruct)
		}
	}
	m.line("")
	m.line("")
	m.line("class %s:", mixin)
	m.in()
	var mine []*Query
	for _, q := range qs {
		if !q.isBatch() && q.Cmd != ":copyfrom" && q.hasMethod() {
			mine = append(mine, q)
		}
	}
	m.mixinPrelude(mine)
	for _, q := range mine {
		m.queryMethod(q)
	}
	m.out()
	return m.render()
}

func (g *generator) renderBatch(l *layout) string {
	m := g.newModule(l.batch, "")
	var qs []*Query
	for _, q := range g.queries {
		if q.isBatch() {
			qs = append(qs, q)
		}
	}
	for _, q := range qs {
		if q.ArgStruct != nil {
			m.registerStructScope(q.ArgStruct)
			m.moduleNames[q.ArgStruct.Name] = true
		}
		if q.EmitRet {
			m.registerStructScope(q.RetStruct)
			m.moduleNames[q.RetStruct.Name] = true
		}
		m.classScope[q.Method] = true
		m.moduleNames[q.Const] = true
	}
	m.moduleNames["BatchQueries"] = true
	m.moduleNames["_batch_conn"] = true
	m.addImport("asyncpg")
	m.addImport("contextlib")
	m.addImport("collections.abc")
	m.addImport("typing")
	for _, q := range qs {
		m.sqlConst(q)
		if q.ArgStruct != nil {
			m.structDef(q.ArgStruct)
		}
		if q.EmitRet {
			m.structDef(q.RetStruct)
		}
	}
	m.line("")
	m.line("")
	m.line("@%s.asynccontextmanager", m.expr("contextlib"))
	m.line("async def _batch_conn(db: \"DBTX\") -> %s.AsyncGenerator[%s.Any, None]:", m.expr("collections")+".abc", m.expr("typing"))
	m.in()
	m.line(`"""Yield one connection inside a transaction."""`)
	m.line("_db: %s.Any = db", m.expr("typing"))
	m.line("if isinstance(db, %s.Pool):", m.expr("asyncpg"))
	m.in()
	m.line("async with _db.acquire() as _c, _c.transaction():")
	m.in()
	m.line("yield _c")
	m.out()
	m.out()
	m.line("else:")
	m.in()
	m.line("async with _db.transaction():")
	m.in()
	m.line("yield _db")
	m.out()
	m.out()
	m.out()
	m.line("")
	m.line("")
	m.line("class BatchQueries:")
	m.in()
	m.mixinPrelude(qs)
	for _, q := range qs {
		m.batchMethod(q)
	}
	m.out()
	return m.render()
}

func (m *pyModule) batchMethod(q *Query) {
	mc := m.newMethodCtx(q)
	m.methodHeader(mc)
	c := m.expr(q.Const)
	vals := m.argValues(mc, "_a")
	tuple := "(" + strings.Join(vals, ", ") + ",)"
	if len(vals) > 1 {
		tuple = "(" + strings.Join(vals, ", ") + ")"
	}
	prepared := m.g.opts.EmitPreparedQueries
	switch q.Cmd {
	case ":batchexec":
		if prepared {
			m.line("_stmt = self._stmts.get(%s)", c)
			m.line("if _stmt is not None:")
			m.in()
			m.line("await _stmt.executemany([%s for _a in %s])", tuple, mc.argVar)
			m.out()
			m.line("else:")
			m.in()
			m.line("await %s.executemany(%s, [%s for _a in %s])", mc.conn, c, tuple, mc.argVar)
			m.out()
		} else {
			m.line("await %s.executemany(%s, [%s for _a in %s])", mc.conn, c, tuple, mc.argVar)
		}
	case ":batchone", ":batchmany":
		m.line("_out: %s = []", m.methodReturn(q))
		if !prepared {
			m.line("async with _batch_conn(%s) as _tx:", mc.conn)
			m.in()
			m.line("_stmt = await _tx.prepare(%s)", c)
		} else {
			m.line("async with _batch_conn(%s) as _tx:", mc.conn)
			m.in()
			m.line("_stmt = self._stmts.get(%s)", c)
			m.line("if _stmt is None:")
			m.in()
			m.line("_stmt = await _tx.prepare(%s)", c)
			m.out()
		}
		m.line("for _a in %s:", mc.argVar)
		m.in()
		if q.Cmd == ":batchone" {
			m.line("_row = await _stmt.fetchrow(%s)", strings.Join(vals, ", "))
			m.line("_out.append(None if _row is None else %s)", m.rowExpr(q, "_row"))
		} else {
			m.line("_rows = await _stmt.fetch(%s)", strings.Join(vals, ", "))
			m.line("_out.append([%s for _r in _rows])", m.rowExpr(q, "_r"))
		}
		m.out()
		m.out()
		m.line("return _out")
	}
	m.methodFooter(mc)
}

func (g *generator) renderCopyFrom(l *layout) string {
	m := g.newModule(l.copyfrom, "")
	var qs []*Query
	for _, q := range g.queries {
		if q.Cmd == ":copyfrom" {
			qs = append(qs, q)
			m.classScope[q.Method] = true
		}
	}
	m.moduleNames["CopyFromQueries"] = true
	for _, q := range qs {
		if q.CopyFallback {
			m.sqlConst(q)
		}
	}
	m.line("")
	m.line("")
	m.line("class CopyFromQueries:")
	m.in()
	m.mixinPrelude(nil)
	for _, q := range qs {
		mc := m.newMethodCtx(q)
		m.methodHeader(mc)
		var cols []string
		if q.ArgKind == argSingle {
			f := q.ArgFields[0]
			name := f.DBName
			if f.Column != nil && f.Column.OriginalName != "" {
				name = f.Column.OriginalName
			}
			cols = append(cols, pyStr(name))
		} else {
			for _, f := range q.ArgStruct.Fields {
				name := f.DBName
				if f.Column != nil && f.Column.OriginalName != "" {
					name = f.Column.OriginalName
				}
				cols = append(cols, pyStr(name))
			}
		}
		var vals []string
		if q.ArgKind == argSingle {
			vals = []string{"_a"}
		} else {
			for _, f := range q.ArgStruct.Fields {
				vals = append(vals, "_a."+f.Name)
			}
		}
		tuple := "(" + strings.Join(vals, ", ") + ",)"
		if len(vals) > 1 {
			tuple = "(" + strings.Join(vals, ", ") + ")"
		}
		colTuple := "(" + strings.Join(cols, ", ") + ",)"
		if len(cols) > 1 {
			colTuple = "(" + strings.Join(cols, ", ") + ")"
		}
		if q.CopyFallback {
			m.line("# No binary COPY encoder for some column types; use executemany.")
			m.line("_records = [%s for _a in %s]", tuple, mc.argVar)
			m.line("await %s.executemany(%s, _records)", mc.conn, m.expr(q.Const))
			m.line("return len(_records)")
			m.methodFooter(mc)
			continue
		}
		schema := "None"
		if q.Table.Schema != "" {
			schema = pyStr(q.Table.Schema)
		}
		m.line("_status = await %s.copy_records_to_table(", mc.conn)
		m.in()
		m.line("%s,", pyStr(q.Table.Name))
		m.line("schema_name=%s,", schema)
		m.line("columns=%s,", colTuple)
		m.line("records=[%s for _a in %s],", tuple, mc.argVar)
		m.out()
		m.line(")")
		m.line(`_n = _status.rpartition(" ")[2]`)
		m.line("return int(_n) if _n.isdigit() else 0")
		m.methodFooter(mc)
	}
	m.out()
	return m.render()
}

func (g *generator) renderDB(l *layout) string {
	m := g.newModule(l.db, "")
	m.addImport("typing")
	m.addImport("collections.abc")
	m.line("")
	m.line("")
	m.line("class DBTX(%s.Protocol):", m.expr("typing"))
	m.in()
	m.line(`"""asyncpg.Connection or asyncpg.Pool."""`)
	m.line("")
	m.line("async def execute(self, query: str, *args: typing.Any, timeout: float | None = ...) -> str: ...")
	m.line("async def executemany(")
	m.line("    self, command: str, args: collections.abc.Iterable[collections.abc.Sequence[typing.Any]], *, timeout: float | None = ...")
	m.line(") -> None: ...")
	m.line("async def fetch(self, query: str, *args: typing.Any, timeout: float | None = ...) -> list[typing.Any]: ...")
	m.line("async def fetchrow(self, query: str, *args: typing.Any, timeout: float | None = ...) -> typing.Any: ...")
	if g.usesCopyFrom() {
		m.line("async def copy_records_to_table(")
		m.line("    self,")
		m.line("    table_name: str,")
		m.line("    *,")
		m.line("    records: collections.abc.Iterable[collections.abc.Sequence[typing.Any]],")
		m.line("    columns: collections.abc.Iterable[str] | None = ...,")
		m.line("    schema_name: str | None = ...,")
		m.line("    timeout: float | None = ...,")
		m.line(") -> str: ...")
	}
	if g.opts.EmitPreparedQueries {
		m.line("async def prepare(self, query: str) -> typing.Any: ...")
	}
	m.out()

	var bases []string
	for _, mod := range l.queryModules {
		hasMethods := false
		for _, q := range g.queries {
			if q.Module == mod && !q.isBatch() && q.Cmd != ":copyfrom" && q.hasMethod() {
				hasMethods = true
			}
		}
		if hasMethods {
			m.addFrom("."+mod, l.queryMixin[mod])
			bases = append(bases, l.queryMixin[mod])
		}
	}
	if g.usesBatch() {
		m.addFrom("."+l.batch, "BatchQueries")
		bases = append(bases, "BatchQueries")
	}
	if g.usesCopyFrom() {
		m.addFrom("."+l.copyfrom, "CopyFromQueries")
		bases = append(bases, "CopyFromQueries")
	}
	m.line("")
	m.line("")
	if len(bases) == 0 {
		m.line("class Queries:")
	} else {
		m.line("class Queries(%s):", strings.Join(bases, ", "))
	}
	m.in()
	if g.dbArg() {
		m.line(`"""Generated queries; each method takes the connection first."""`)
		m.line("")
		m.line("__slots__ = ()")
	} else {
		m.line(`"""Generated queries bound to a connection or pool."""`)
		m.line("")
		if g.opts.EmitPreparedQueries {
			m.line(`__slots__ = ("_conn", "_stmts")`)
		} else {
			m.line(`__slots__ = ("_conn",)`)
		}
		m.line("")
		m.line("def __init__(self, conn: DBTX) -> None:")
		m.in()
		m.line("self._conn = conn")
		if g.opts.EmitPreparedQueries {
			m.line("self._stmts: dict[str, typing.Any] = {}")
		}
		m.out()
		m.line("")
		m.line("def with_tx(self, conn: DBTX) -> typing.Self:")
		m.in()
		m.line(`"""Return a copy bound to conn."""`)
		m.line("q = type(self)(conn)")
		if g.opts.EmitPreparedQueries {
			m.line("if conn is self._conn:")
			m.line("    q._stmts = self._stmts")
		}
		m.line("return q")
		m.out()
	}
	if g.opts.EmitPreparedQueries {
		m.line("")
		m.line("@classmethod")
		m.line("async def prepare(cls, conn: DBTX) -> typing.Self:")
		m.in()
		m.line(`"""Prepare every query on conn."""`)
		m.line("q = cls(conn)")
		m.line("for klass in reversed(cls.__mro__):")
		m.in()
		m.line(`statements = typing.cast(tuple[tuple[str, str], ...], klass.__dict__.get("_sqlc_statements", ()))`)
		m.line("for name, sql in statements:")
		m.in()
		m.line("try:")
		m.line("    q._stmts[sql] = await conn.prepare(sql)")
		m.line("except Exception as e:")
		m.line(`    e.add_note(f"error preparing query {name}")`)
		m.line("    raise")
		m.out()
		m.out()
		m.line("return q")
		m.out()
		m.line("")
		m.line("def close(self) -> None:")
		m.in()
		m.line(`"""Drop prepared statements."""`)
		m.line("self._stmts.clear()")
		m.out()
	}
	m.out()
	return m.render()
}

func (g *generator) renderQuerier(l *layout) string {
	m := g.newModule(l.querier, "")
	m.addImport("typing")
	for _, q := range g.queries {
		m.classScope[q.Method] = true
	}
	if g.dbArg() {
		m.addTypeOnly("."+l.db, "DBTX")
	}
	m.addTypeOnly("."+l.db, "Queries")
	m.line("")
	m.line("")
	m.line("class Querier(%s.Protocol):", m.expr("typing"))
	m.in()
	nMethods := 0
	for _, q := range g.queries {
		if q.hasMethod() {
			nMethods++
		}
	}
	if nMethods == 0 {
		m.line("pass")
	}
	for _, q := range g.queries {
		if !q.hasMethod() {
			continue
		}
		mc := m.newMethodCtx(q)
		sig := m.signature(mc)
		if sig != "" {
			sig = ", " + sig
		}
		m.line("")
		m.line("async def %s(self%s) -> %s:", q.Method, sig, m.methodReturn(q))
		m.in()
		m.docstring(q.Comments)
		m.line("...")
		m.out()
	}
	m.out()
	m.line("")
	m.line("")
	m.line("if %s.TYPE_CHECKING:", m.expr("typing"))
	m.in()
	m.line(`_queries_implements_querier: type[Querier] = Queries`)
	m.out()
	return m.render()
}
