package gen

import (
	"errors"
	"fmt"
	"regexp"
	"strings"

	"github.com/sqlc-dev/plugin-sdk-go/plugin"
)

// pyType is a resolved Python element type (without list / None wrapping).
type pyType struct {
	// Expr is the annotation; "{models}" is replaced per module.
	Expr string
	// Imports: `import x`.
	Imports []string
	// FromImports: `from x import y`.
	FromImports [][2]string
	// Enum is set for generated enums (asyncpg returns str).
	Enum *Enum
	// Unknown marks typing.Any fallbacks.
	Unknown bool
}

// fieldType is a fully resolved column type.
type fieldType struct {
	Elem     *pyType
	Dims     int  // list nesting
	Nullable bool // `| None`
}

func (t fieldType) annotation(modelsPrefix string) string {
	if t.Elem.Expr == "None" && t.Dims == 0 {
		return "None" // void
	}
	s := strings.ReplaceAll(t.Elem.Expr, "{models}", modelsPrefix)
	for range t.Dims {
		s = "list[" + s + "]"
	}
	if t.Nullable {
		s += " | None"
	}
	return s
}

func (t fieldType) key() string {
	return t.annotation("{models}.")
}

func (t fieldType) needsConversion() bool {
	return t.Elem.Enum != nil
}

func dataType(n *plugin.Identifier) string {
	if n == nil {
		return ""
	}
	if n.Schema != "" {
		return n.Schema + "." + n.Name
	}
	return n.Name
}

var dottedName = regexp.MustCompile(`[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+`)

func parsePyType(t PyType) (*pyType, error) {
	if t.Spec == "" && t.Type == "" {
		return nil, errors.New("missing py_type")
	}
	if t.Spec != "" {
		var imports []string
		for _, m := range dottedName.FindAllString(t.Spec, -1) {
			mod := m[:strings.LastIndex(m, ".")]
			imports = append(imports, mod)
		}
		return &pyType{Expr: t.Spec, Imports: imports}, nil
	}
	if !isIdentifier(t.Type) {
		return nil, fmt.Errorf("py_type.type %q must be an identifier", t.Type)
	}
	if t.Import == "" {
		return &pyType{Expr: t.Type}, nil
	}
	return &pyType{Expr: t.Type, FromImports: [][2]string{{t.Import, t.Type}}}, nil
}

func simple(expr string, imports ...string) *pyType {
	return &pyType{Expr: expr, Imports: imports}
}

var anyType = &pyType{Expr: "typing.Any", Imports: []string{"typing"}, Unknown: true}

func rangeOf(inner string, imports ...string) *pyType {
	return &pyType{Expr: "asyncpg.Range[" + inner + "]", Imports: append([]string{"asyncpg"}, imports...)}
}

func multirangeOf(inner string, imports ...string) *pyType {
	return &pyType{Expr: "list[asyncpg.Range[" + inner + "]]", Imports: append([]string{"asyncpg"}, imports...)}
}

// builtinType maps a PostgreSQL type to what asyncpg's default codecs return.
func builtinType(name string) *pyType {
	switch name {
	case "serial", "serial4", "pg_catalog.serial4",
		"bigserial", "serial8", "pg_catalog.serial8",
		"smallserial", "serial2", "pg_catalog.serial2",
		"integer", "int", "int4", "pg_catalog.int4",
		"bigint", "int8", "pg_catalog.int8",
		"smallint", "int2", "pg_catalog.int2",
		"oid", "pg_catalog.oid", "xid", "pg_catalog.xid", "xid8", "pg_catalog.xid8",
		"cid", "pg_catalog.cid", "regproc", "pg_catalog.regproc":
		return simple("int")
	case "float", "double precision", "float8", "pg_catalog.float8",
		"real", "float4", "pg_catalog.float4":
		return simple("float")
	case "numeric", "pg_catalog.numeric", "decimal":
		return simple("decimal.Decimal", "decimal")
	case "money", "pg_catalog.money":
		return simple("str")
	case "boolean", "bool", "pg_catalog.bool":
		return simple("bool")
	case "json", "pg_catalog.json", "jsonb", "pg_catalog.jsonb", "jsonpath", "pg_catalog.jsonpath":
		return simple("str")
	case "bytea", "blob", "pg_catalog.bytea":
		return simple("bytes")
	case "date", "pg_catalog.date":
		return simple("datetime.date", "datetime")
	case "pg_catalog.time", "time", "pg_catalog.timetz", "timetz":
		return simple("datetime.time", "datetime")
	case "pg_catalog.timestamp", "timestamp", "pg_catalog.timestamptz", "timestamptz":
		return simple("datetime.datetime", "datetime")
	case "interval", "pg_catalog.interval":
		return simple("datetime.timedelta", "datetime")
	case "text", "pg_catalog.text", "pg_catalog.varchar", "varchar", "pg_catalog.bpchar", "bpchar",
		"string", "citext", "name", "pg_catalog.name", "pg_catalog.char", "char",
		"ltree", "lquery", "ltxtquery", "macaddr", "pg_catalog.macaddr", "macaddr8", "pg_catalog.macaddr8",
		"tsvector", "pg_catalog.tsvector", "tsquery", "pg_catalog.tsquery", "xml", "pg_catalog.xml",
		"hstore", "vector", "regclass", "pg_catalog.regclass", "regtype", "pg_catalog.regtype",
		"pg_lsn", "pg_catalog.pg_lsn", "txid_snapshot", "pg_snapshot", "pg_catalog.pg_snapshot",
		"unknown":
		return simple("str")
	case "uuid", "pg_catalog.uuid":
		return simple("uuid.UUID", "uuid")
	case "inet", "pg_catalog.inet":
		return simple("ipaddress.IPv4Address | ipaddress.IPv6Address | ipaddress.IPv4Interface | ipaddress.IPv6Interface", "ipaddress")
	case "cidr", "pg_catalog.cidr":
		return simple("ipaddress.IPv4Network | ipaddress.IPv6Network", "ipaddress")
	case "int4range", "pg_catalog.int4range", "int8range", "pg_catalog.int8range":
		return rangeOf("int")
	case "int4multirange", "pg_catalog.int4multirange", "int8multirange", "pg_catalog.int8multirange":
		return multirangeOf("int")
	case "numrange", "pg_catalog.numrange":
		return rangeOf("decimal.Decimal", "decimal")
	case "nummultirange", "pg_catalog.nummultirange":
		return multirangeOf("decimal.Decimal", "decimal")
	case "daterange", "pg_catalog.daterange":
		return rangeOf("datetime.date", "datetime")
	case "datemultirange", "pg_catalog.datemultirange":
		return multirangeOf("datetime.date", "datetime")
	case "tsrange", "pg_catalog.tsrange", "tstzrange", "pg_catalog.tstzrange":
		return rangeOf("datetime.datetime", "datetime")
	case "tsmultirange", "pg_catalog.tsmultirange", "tstzmultirange", "pg_catalog.tstzmultirange":
		return multirangeOf("datetime.datetime", "datetime")
	case "bit", "varbit", "pg_catalog.bit", "pg_catalog.varbit":
		return simple("asyncpg.BitString", "asyncpg")
	case "tid", "pg_catalog.tid":
		return simple("tuple[int, int]")
	case "point", "pg_catalog.point":
		return simple("asyncpg.Point", "asyncpg")
	case "box", "pg_catalog.box":
		return simple("asyncpg.Box", "asyncpg")
	case "circle", "pg_catalog.circle":
		return simple("asyncpg.Circle", "asyncpg")
	case "line", "pg_catalog.line":
		return simple("asyncpg.Line", "asyncpg")
	case "lseg", "pg_catalog.lseg":
		return simple("asyncpg.LineSegment", "asyncpg")
	case "path", "pg_catalog.path":
		return simple("asyncpg.Path", "asyncpg")
	case "polygon", "pg_catalog.polygon":
		return simple("asyncpg.Polygon", "asyncpg")
	case "void", "pg_catalog.void":
		return simple("None")
	}
	return nil
}

func parseIdentifierString(name string) (*plugin.Identifier, error) {
	parts := strings.Split(name, ".")
	switch len(parts) {
	case 1:
		return &plugin.Identifier{Name: parts[0]}, nil
	case 2:
		return &plugin.Identifier{Schema: parts[0], Name: parts[1]}, nil
	case 3:
		return &plugin.Identifier{Catalog: parts[0], Schema: parts[1], Name: parts[2]}, nil
	}
	return nil, fmt.Errorf("invalid name: %s", name)
}

// innerType resolves the element type of a column (goInnerType).
func (g *generator) innerType(col *plugin.Column) *pyType {
	for i := range g.opts.Overrides {
		o := &g.opts.Overrides[i]
		if o.matchesDBType(col) {
			return o.typ
		}
	}
	name := dataType(col.Type)
	if t := builtinType(name); t != nil {
		return t
	}
	rel, err := parseIdentifierString(name)
	if err != nil {
		return anyType
	}
	if rel.Schema == "" {
		rel.Schema = g.defaultSchema
	}
	for _, schema := range g.req.Catalog.GetSchemas() {
		if schema.Name == "pg_catalog" || schema.Name == "information_schema" {
			continue
		}
		if schema.Name != rel.Schema {
			continue
		}
		for _, e := range schema.Enums {
			if e.Name == rel.Name {
				en := g.enumByKey[schema.Name+"."+e.Name]
				return &pyType{Expr: "{models}" + en.Name, Enum: en}
			}
		}
	}
	return anyType
}

// columnType resolves the full type of a column (goType).
func (g *generator) columnType(col *plugin.Column) fieldType {
	nullable := !col.NotNull
	dims := 0
	if col.IsArray {
		dims = max(int(col.ArrayDims), 1)
	}
	if col.IsSqlcSlice {
		dims = 1
		nullable = false
	}
	for i := range g.opts.Overrides {
		o := &g.opts.Overrides[i]
		if o.typ != nil && o.matchesColumn(col, g.defaultSchema) {
			return fieldType{Elem: o.typ, Dims: dims, Nullable: nullable}
		}
	}
	return fieldType{Elem: g.innerType(col), Dims: dims, Nullable: nullable}
}
