package gen

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"maps"
	"sort"
	"strconv"
	"strings"

	"github.com/sqlc-dev/plugin-sdk-go/pattern"
	"github.com/sqlc-dev/plugin-sdk-go/plugin"
)

// Options mirror sqlc's Go generator options. Go-only options are rejected.
type Options struct {
	EmitJSONTags                bool              `json:"emit_json_tags"`
	JSONTagsIDUppercase         bool              `json:"json_tags_id_uppercase"`
	JSONTagsCaseStyle           string            `json:"json_tags_case_style"`
	EmitExactTableNames         bool              `json:"emit_exact_table_names"`
	EmitEmptySlices             bool              `json:"emit_empty_slices"` // accepted; Python always returns lists
	EmitExportedQueries         bool              `json:"emit_exported_queries"`
	EmitEnumValidMethod         bool              `json:"emit_enum_valid_method"`
	EmitAllEnumValues           bool              `json:"emit_all_enum_values"`
	EmitSQLAsComment            bool              `json:"emit_sql_as_comment"`
	Overrides                   []Override        `json:"overrides"`
	Rename                      map[string]string `json:"rename"`
	OutputBatchFileName         string            `json:"output_batch_file_name"`
	OutputDBFileName            string            `json:"output_db_file_name"`
	OutputModelsFileName        string            `json:"output_models_file_name"`
	OutputCopyfromFileName      string            `json:"output_copyfrom_file_name"`
	OutputFilesSuffix           string            `json:"output_files_suffix"`
	InflectionExcludeTableNames []string          `json:"inflection_exclude_table_names"`
	WrapErrors                  bool              `json:"wrap_errors"`
	QueryParameterLimit         *int32            `json:"query_parameter_limit"`
	OmitSqlcVersion             bool              `json:"omit_sqlc_version"`
	OmitUnusedStructs           bool              `json:"omit_unused_structs"`
	Initialisms                 *[]string         `json:"initialisms"`
	// MsgspecStructOptions are class keywords for every msgspec.Struct.
	MsgspecStructOptions map[string]any `json:"msgspec_struct_options"`

	initialisms map[string]struct{}
}

// GlobalOptions come from the top-level `options.<plugin name>` block.
type GlobalOptions struct {
	Overrides []Override        `json:"overrides"`
	Rename    map[string]string `json:"rename"`
}

// PyType is an override type: an expression ("dict[str, typing.Any]") or
// {"import": "pkg.mod", "type": "Name"}.
type PyType struct {
	Spec   string // string form
	Import string `json:"import"`
	Type   string `json:"type"`
}

func (t *PyType) UnmarshalJSON(b []byte) error {
	var s string
	if err := json.Unmarshal(b, &s); err == nil {
		t.Spec = s
		return nil
	}
	var obj struct {
		Import string `json:"import"`
		Type   string `json:"type"`
	}
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&obj); err != nil {
		return fmt.Errorf("py_type must be a string or an object with \"import\" and \"type\": %w", err)
	}
	t.Import = obj.Import
	t.Type = obj.Type
	return nil
}

type Override struct {
	PyType   PyType `json:"py_type"`
	DBType   string `json:"db_type"`
	Column   string `json:"column"`
	Nullable bool   `json:"nullable"`
	Unsigned bool   `json:"unsigned"`
	Engine   string `json:"engine"`

	columnName   *pattern.Match
	tableCatalog *pattern.Match
	tableSchema  *pattern.Match
	tableRel     *pattern.Match
	typ          *pyType
}

func decodeStrict(data []byte, v any) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return err
	}
	if dec.More() {
		return errors.New("unexpected trailing data")
	}
	return nil
}

func parseOptions(req *plugin.GenerateRequest) (*Options, error) {
	var o Options
	if len(req.PluginOptions) > 0 {
		if err := decodeStrict(req.PluginOptions, &o); err != nil {
			return nil, fmt.Errorf("invalid plugin options: %w", err)
		}
	}
	var g GlobalOptions
	if len(req.GlobalOptions) > 0 {
		if err := decodeStrict(req.GlobalOptions, &g); err != nil {
			return nil, fmt.Errorf("invalid global options: %w", err)
		}
	}
	if len(g.Overrides) > 0 {
		o.Overrides = append(append([]Override{}, g.Overrides...), o.Overrides...)
	}
	if len(g.Rename) > 0 {
		if o.Rename == nil {
			o.Rename = map[string]string{}
		}
		maps.Copy(o.Rename, g.Rename)
	}

	defaultSchema := "public"
	if req.Catalog != nil && req.Catalog.DefaultSchema != "" {
		defaultSchema = req.Catalog.DefaultSchema
	}
	engine := ""
	if req.Settings != nil {
		engine = req.Settings.Engine
	}
	if engine != "" && engine != "postgresql" {
		return nil, fmt.Errorf("sqlc-gen-asyncpg only supports the postgresql engine, got %q", engine)
	}

	kept := o.Overrides[:0]
	for i := range o.Overrides {
		ov := o.Overrides[i]
		if ov.Engine != "" && ov.Engine != "postgresql" {
			continue
		}
		if err := ov.parse(defaultSchema); err != nil {
			return nil, err
		}
		kept = append(kept, ov)
	}
	o.Overrides = kept

	if o.QueryParameterLimit == nil {
		v := int32(1)
		o.QueryParameterLimit = &v
	}
	if *o.QueryParameterLimit < 0 {
		return nil, errors.New("invalid options: query parameter limit must not be negative")
	}
	switch o.JSONTagsCaseStyle {
	case "", "none", "camel", "pascal", "snake":
	default:
		return nil, fmt.Errorf("invalid options: unsupported json_tags_case_style %q (expected camel, pascal, snake or none)", o.JSONTagsCaseStyle)
	}
	o.initialisms = map[string]struct{}{}
	if o.Initialisms != nil {
		for _, s := range *o.Initialisms {
			o.initialisms[s] = struct{}{}
		}
	}
	for k, v := range o.Rename {
		if !isIdentifier(v) || isKeyword(v) || strings.HasPrefix(v, "__") {
			return nil, fmt.Errorf("invalid options: rename %q -> %q is not a valid Python identifier", k, v)
		}
	}
	keys := make([]string, 0, len(o.MsgspecStructOptions))
	for k := range o.MsgspecStructOptions {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		if !isIdentifier(k) {
			return nil, fmt.Errorf("invalid options: msgspec_struct_options key %q is not an identifier", k)
		}
		if _, err := pyLiteral(o.MsgspecStructOptions[k]); err != nil {
			return nil, fmt.Errorf("invalid options: msgspec_struct_options.%s: %w", k, err)
		}
		if k == "rename" && o.EmitJSONTags {
			return nil, errors.New("invalid options: msgspec_struct_options.rename cannot be combined with emit_json_tags")
		}
	}
	for name, v := range map[string]string{
		"output_batch_file_name":    o.OutputBatchFileName,
		"output_db_file_name":       o.OutputDBFileName,
		"output_models_file_name":   o.OutputModelsFileName,
		"output_copyfrom_file_name": o.OutputCopyfromFileName,
	} {
		if v == "" {
			continue
		}
		if !isIdentifier(strings.TrimSuffix(v, ".py")) {
			return nil, fmt.Errorf("invalid options: %s %q must be a valid Python module file name", name, v)
		}
	}
	if o.OutputFilesSuffix != "" && !isIdentifier("x"+strings.TrimSuffix(o.OutputFilesSuffix, ".py")) {
		return nil, fmt.Errorf("invalid options: output_files_suffix %q must only contain identifier characters", o.OutputFilesSuffix)
	}
	return &o, nil
}

func pyLiteral(v any) (string, error) {
	switch x := v.(type) {
	case bool:
		if x {
			return "True", nil
		}
		return "False", nil
	case string:
		return pyStr(x), nil
	case float64:
		if x == float64(int64(x)) {
			return strconv.FormatInt(int64(x), 10), nil
		}
		return fmt.Sprintf("%v", x), nil
	case nil:
		return "None", nil
	case []any:
		parts := make([]string, len(x))
		for i, e := range x {
			s, err := pyLiteral(e)
			if err != nil {
				return "", err
			}
			parts[i] = s
		}
		if len(parts) == 1 {
			return "(" + parts[0] + ",)", nil
		}
		return "(" + strings.Join(parts, ", ") + ")", nil
	case map[string]any:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		parts := make([]string, len(keys))
		for i, k := range keys {
			s, err := pyLiteral(x[k])
			if err != nil {
				return "", err
			}
			parts[i] = pyStr(k) + ": " + s
		}
		return "{" + strings.Join(parts, ", ") + "}", nil
	default:
		return "", fmt.Errorf("unsupported value %v", v)
	}
}

func (o *Override) parse(defaultSchema string) (err error) {
	switch {
	case o.Column != "" && o.DBType != "":
		return fmt.Errorf("override specifying both `column` (%q) and `db_type` (%q) is not valid", o.Column, o.DBType)
	case o.Column == "" && o.DBType == "":
		return errors.New("override must specify one of either `column` or `db_type`")
	}
	if o.Column != "" {
		parts := strings.Split(o.Column, ".")
		var cat, sch, rel, col string
		switch len(parts) {
		case 2:
			sch, rel, col = defaultSchema, parts[0], parts[1]
		case 3:
			sch, rel, col = parts[0], parts[1], parts[2]
		case 4:
			cat, sch, rel, col = parts[0], parts[1], parts[2], parts[3]
		default:
			return fmt.Errorf("override `column` specifier %q is not the proper format, expected '[catalog.][schema.]tablename.colname'", o.Column)
		}
		if o.columnName, err = pattern.MatchCompile(col); err != nil {
			return err
		}
		if o.tableRel, err = pattern.MatchCompile(rel); err != nil {
			return err
		}
		if o.tableSchema, err = pattern.MatchCompile(sch); err != nil {
			return err
		}
		if len(parts) == 4 {
			if o.tableCatalog, err = pattern.MatchCompile(cat); err != nil {
				return err
			}
		}
	}
	t, err := parsePyType(o.PyType)
	if err != nil {
		return fmt.Errorf("override %s: %w", o.describe(), err)
	}
	o.typ = t
	return nil
}

func (o *Override) describe() string {
	if o.Column != "" {
		return "column " + o.Column
	}
	return "db_type " + o.DBType
}

// matchesTable mirrors sqlc's Override.Matches.
func (o *Override) matchesTable(n *plugin.Identifier, defaultSchema string) bool {
	if n == nil {
		return false
	}
	schema := n.Schema
	if schema == "" {
		schema = defaultSchema
	}
	if o.tableCatalog != nil && !o.tableCatalog.MatchString(n.Catalog) {
		return false
	}
	if o.tableSchema == nil && schema != "" {
		return false
	}
	if o.tableSchema != nil && !o.tableSchema.MatchString(schema) {
		return false
	}
	if o.tableRel == nil && n.Name != "" {
		return false
	}
	if o.tableRel != nil && !o.tableRel.MatchString(n.Name) {
		return false
	}
	return true
}

// matchesDBType mirrors sqlc's Override.MatchesColumn.
func (o *Override) matchesDBType(col *plugin.Column) bool {
	notNull := col.NotNull || col.IsArray
	return o.DBType != "" && o.DBType == dataType(col.Type) && o.Nullable != notNull && o.Unsigned == col.Unsigned
}

func (o *Override) matchesColumn(col *plugin.Column, defaultSchema string) bool {
	if o.Column == "" {
		return false
	}
	name := col.Name
	if col.OriginalName != "" {
		name = col.OriginalName
	}
	return o.columnName.MatchString(name) && o.matchesTable(col.Table, defaultSchema)
}
