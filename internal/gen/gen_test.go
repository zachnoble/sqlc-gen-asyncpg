package gen

import (
	"encoding/json"
	"math/rand"
	"os/exec"
	"strings"
	"testing"

	"github.com/sqlc-dev/plugin-sdk-go/plugin"
)

func TestSnakeCase(t *testing.T) {
	cases := map[string]string{
		"GetAuthor":        "get_author",
		"GetAuthorByID":    "get_author_by_id",
		"AuthorsByIDs":     "authors_by_ids",
		"ListURLs":         "list_urls",
		"getHTTPResponse":  "get_http_response",
		"get_snake_case":   "get_snake_case",
		"ListAuthorsV2":    "list_authors_v2",
		"A":                "a",
		"ID":               "id",
		"IDs":              "ids",
		"UpdateBios":       "update_bios",
		"HTTPServer":       "http_server",
		"Get2FACodes":      "get2_fa_codes",
		"already_Snake_X":  "already_snake_x",
		"ÜberQuery":        "über_query",
		"CreateUserTwo":    "create_user_two",
		"BatchGetIDsByURL": "batch_get_ids_by_url",
	}
	for in, want := range cases {
		if got := snakeCase(in); got != want {
			t.Errorf("snakeCase(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestSanitize(t *testing.T) {
	cases := map[string]string{
		"name":       "name",
		"first name": "first_name",
		"2fa":        "_2fa",
		"class":      "class_",
		"None":       "None_",
		"__secret":   "_secret",
		"___":        "_x",
		"":           "_",
		"café":       "café",
		"a-b.c":      "a_b_c",
		"?column?":   "_column_",
		"_row":       "_row",
	}
	for in, want := range cases {
		if got := sanitize(in); got != want {
			t.Errorf("sanitize(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestEnumMemberName(t *testing.T) {
	cases := map[string]string{
		"open":        "OPEN",
		"in-progress": "IN_PROGRESS",
		"a b":         "A_B",
		"a/b:c":       "A_B_C",
		"it's":        "ITS",
		"ñ":           "",
	}
	for in, want := range cases {
		if got := enumMemberName(in); got != want {
			t.Errorf("enumMemberName(%q) = %q, want %q", in, got, want)
		}
	}
	for _, bad := range []string{"", "_X", "1ST"} {
		if validEnumMember(bad) {
			t.Errorf("validEnumMember(%q) should be false", bad)
		}
	}
}

func TestSingular(t *testing.T) {
	cases := map[string]string{
		"users": "user", "people": "person", "campus": "campus", "meta": "meta",
		"calories": "calorie", "waves": "wave", "metadata": "metadata", "news": "news",
	}
	for in, want := range cases {
		if got := singular(in, nil); got != want {
			t.Errorf("singular(%q) = %q, want %q", in, got, want)
		}
	}
	if got := singular("Users", []string{"users"}); got != "Users" {
		t.Errorf("exclusion should be case-insensitive, got %q", got)
	}
}

func TestRewriteSlices(t *testing.T) {
	p := func(n int32, slice bool) *plugin.Parameter {
		return &plugin.Parameter{Number: n, Column: &plugin.Column{IsSqlcSlice: slice}}
	}
	cases := []struct{ in, want string }{
		{"WHERE id IN ($1)", "WHERE id = ANY($1)"},
		{"WHERE id in ( $1 )", "WHERE id = ANY($1)"},
		{"WHERE id NOT IN ($1)", "WHERE id <> ALL($1)"},
		{"WHERE id not\n  in ($1)", "WHERE id <> ALL($1)"},
		{"WHERE id IN ($10)", "WHERE id IN ($10)"}, // not $1
		{"WHERE a IN ($1) AND b IN ($2)", "WHERE a = ANY($1) AND b IN ($2)"},
	}
	for _, c := range cases {
		got := rewriteSlices(c.in, []*plugin.Parameter{p(1, true), p(2, false)})
		if got != c.want {
			t.Errorf("rewriteSlices(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

// TestStringLiterals renders random strings as Python literals and checks a
// real Python interpreter evaluates them back to the exact same text.
func TestStringLiterals(t *testing.T) {
	py, err := exec.LookPath("python3")
	if err != nil {
		t.Skip("python3 not available")
	}
	alphabet := []rune("\"\"\"''\\\\\n\r\t\x00\x01\x0b\x0c\x7f\u2028\u2029\ufeff aé🎉$`{}%")
	rng := rand.New(rand.NewSource(1))
	var inputs []string
	inputs = append(inputs, "", `"`, `""`, `"""`, `""""`, `\`, `\"`, "a\"", "\"\"\"\"\"\"\"", "x\\", "\\\"\"\"")
	for range 3000 {
		n := rng.Intn(12)
		var b strings.Builder
		for range n {
			b.WriteRune(alphabet[rng.Intn(len(alphabet))])
		}
		inputs = append(inputs, b.String())
	}
	var src strings.Builder
	src.WriteString("import json, sys\nout = []\n")
	for _, s := range inputs {
		src.WriteString("out.append(")
		src.WriteString(pyTripleStr(s))
		src.WriteString(")\n")

		src.WriteString("out.append(")
		src.WriteString(pyStr(s))
		src.WriteString(")\n")
	}
	src.WriteString("sys.stdout.write(json.dumps(out))\n")

	cmd := exec.Command(py, "-I", "-")
	cmd.Stdin = strings.NewReader(src.String())
	outb, err := cmd.Output()
	if err != nil {
		t.Fatalf("python failed: %v", err)
	}
	var got []string
	if err := json.Unmarshal(outb, &got); err != nil {
		t.Fatal(err)
	}
	for i, s := range inputs {
		if got[2*i] != s {
			t.Errorf("triple literal for %q evaluated to %q", s, got[2*i])
		}
		if got[2*i+1] != s {
			t.Errorf("literal for %q evaluated to %q", s, got[2*i+1])
		}
	}
}

func TestOptionErrors(t *testing.T) {
	cases := map[string]string{
		`{"emit_db_tags": true}`:                             `unknown field "emit_db_tags"`,
		`{"query_parameter_limit": -1}`:                      "must not be negative",
		`{"json_tags_case_style": "kebab"}`:                  "unsupported json_tags_case_style",
		`{"rename": {"a": "__x"}}`:                           "not a valid Python identifier",
		`{"overrides": [{"db_type": "text"}]}`:               "missing py_type",
		`{"overrides": [{"db_type": "text", "py_type": 1}]}`: "py_type must be",
		`{"output_files_suffix": "-x"}`:                      "identifier characters",
	}
	for opts, want := range cases {
		req := &plugin.GenerateRequest{PluginOptions: []byte(opts), Settings: &plugin.Settings{Engine: "postgresql"}}
		_, err := parseOptions(req)
		if err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("options %s: got error %v, want %q", opts, err, want)
		}
	}
	req := &plugin.GenerateRequest{Settings: &plugin.Settings{Engine: "mysql"}}
	if _, err := parseOptions(req); err == nil || !strings.Contains(err.Error(), "only supports the postgresql engine") {
		t.Errorf("mysql engine should be rejected, got %v", err)
	}
}

func TestParsePyType(t *testing.T) {
	pt, err := parsePyType(PyType{Spec: "dict[str, typing.Any] | collections.abc.Sequence[my.pkg.T]"})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"typing", "collections.abc", "my.pkg"}
	if strings.Join(pt.Imports, ",") != strings.Join(want, ",") {
		t.Errorf("imports = %v, want %v", pt.Imports, want)
	}
	pt, err = parsePyType(PyType{Import: "a.b", Type: "C"})
	if err != nil || pt.Expr != "C" || pt.FromImports[0] != [2]string{"a.b", "C"} {
		t.Errorf("object form parsed wrong: %+v %v", pt, err)
	}
}

func TestNormalizeBlankLines(t *testing.T) {
	in := "import x\nclass A:\n    a: int\n\n\n\n    def f(self):\n        pass\nX = 1\nY = \"\"\"\n\n\n\nkeep\"\"\"\n"
	want := "import x\n\n\nclass A:\n    a: int\n\n    def f(self):\n        pass\n\n\nX = 1\nY = \"\"\"\n\n\n\nkeep\"\"\"\n"
	if got := normalizeBlankLines(in); got != want {
		t.Errorf("got:\n%s\nwant:\n%s", got, want)
	}
}

func TestClassName(t *testing.T) {
	g := &generator{opts: &Options{initialisms: map[string]struct{}{"id": {}, "url": {}}, Rename: map[string]string{"weird": "Renamed"}}}
	cases := map[string]string{
		"user_id":     "UserID",
		"short_url":   "ShortURL",
		"users":       "Users",
		"weird":       "Renamed",
		"1st_table":   "_1stTable",
		"my schema.x": "MySchemaX",
		"class":       "Class",
	}
	for in, want := range cases {
		if got := g.className(in); got != want {
			t.Errorf("className(%q) = %q, want %q", in, got, want)
		}
	}
	g.opts.initialisms = map[string]struct{}{}
	if got := g.className("user_id"); got != "UserId" {
		t.Errorf("without initialisms got %q", got)
	}
}
