package gen

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// pyModule accumulates one generated Python file.
type pyModule struct {
	g        *generator
	name     string // module name without .py
	source   string // for the header
	isModels bool

	imports     map[string]bool
	fromImports map[string]map[string]bool
	relImports  map[string]bool // from . import x
	typeOnly    map[string]map[string]bool

	// classScope holds every name bound inside a class body of this module
	// (struct fields, methods, enum members). Annotation roots that collide
	// with one of them are referenced through a module level alias, because
	// on Python 3.14+ (PEP 649) annotations are resolved in the class
	// namespace where msgspec field descriptors shadow module globals.
	classScope map[string]bool
	aliases    map[string]string
	// moduleNames are all names bound at module level (used to keep method
	// parameter names from shadowing anything the body references).
	moduleNames map[string]bool

	b      strings.Builder
	indent int

	needEnumHelper  bool
	needArrayHelper bool
}

func (g *generator) newModule(name, source string) *pyModule {
	return &pyModule{
		g:           g,
		name:        name,
		source:      source,
		imports:     map[string]bool{},
		fromImports: map[string]map[string]bool{},
		relImports:  map[string]bool{},
		typeOnly:    map[string]map[string]bool{},
		classScope:  map[string]bool{},
		aliases:     map[string]string{},
		moduleNames: map[string]bool{},
	}
}

func (m *pyModule) line(format string, args ...any) {
	s := format
	if len(args) > 0 {
		s = fmt.Sprintf(format, args...)
	}
	if s == "" {
		m.b.WriteString("\n")
		return
	}
	for i, l := range strings.Split(s, "\n") {
		_ = i
		if l == "" {
			m.b.WriteString("\n")
			continue
		}
		m.b.WriteString(strings.Repeat("    ", m.indent))
		m.b.WriteString(l)
		m.b.WriteString("\n")
	}
}

// raw writes text without applying indentation to continuation lines
// (used for multi-line string literals).
func (m *pyModule) raw(s string) {
	m.b.WriteString(strings.Repeat("    ", m.indent))
	m.b.WriteString(s)
	m.b.WriteString("\n")
}

func (m *pyModule) in()  { m.indent++ }
func (m *pyModule) out() { m.indent-- }

func (m *pyModule) docstring(lines []string) {
	var trimmed []string
	for _, l := range lines {
		trimmed = append(trimmed, strings.TrimRight(l, " \t\r"))
	}
	for len(trimmed) > 0 && trimmed[0] == "" {
		trimmed = trimmed[1:]
	}
	for len(trimmed) > 0 && trimmed[len(trimmed)-1] == "" {
		trimmed = trimmed[:len(trimmed)-1]
	}
	if len(trimmed) == 0 {
		return
	}
	ind := strings.Repeat("    ", m.indent)
	lit := pyTripleStr(strings.Join(trimmed, "\n"))
	// indent continuation lines like a hand written docstring; the
	// literal never contains raw newlines other than line breaks.
	parts := strings.Split(lit, "\n")
	for i := 1; i < len(parts); i++ {
		if parts[i] != "" {
			parts[i] = ind + parts[i]
		}
	}
	if len(parts) > 1 {
		parts[len(parts)-1] = strings.TrimSuffix(parts[len(parts)-1], `"""`)
		parts = append(parts, ind+`"""`)
	}
	m.raw(strings.Join(parts, "\n"))
}

func (m *pyModule) addImport(mod string) {
	m.imports[mod] = true
}

func (m *pyModule) addFrom(mod, name string) {
	if m.fromImports[mod] == nil {
		m.fromImports[mod] = map[string]bool{}
	}
	m.fromImports[mod][name] = true
}

func (m *pyModule) addTypeOnly(mod, name string) {
	if m.typeOnly[mod] == nil {
		m.typeOnly[mod] = map[string]bool{}
	}
	m.typeOnly[mod][name] = true
}

var rootIdent = regexp.MustCompile(`(^|[^.\w])([A-Za-z_]\w*)`)

// ref rewrites the root identifiers of an expression through the alias table.
func (m *pyModule) ref(expr string) string {
	return rootIdent.ReplaceAllStringFunc(expr, func(s string) string {
		sub := rootIdent.FindStringSubmatch(s)
		if a, ok := m.aliases[sub[2]]; ok {
			return sub[1] + a
		}
		return s
	})
}

// aliasFor registers an alias for a module level name if it is shadowed in
// some class scope of this module.
func (m *pyModule) aliasFor(name string) (string, bool) {
	if !m.classScope[name] {
		return "", false
	}
	if a, ok := m.aliases[name]; ok {
		return a, true
	}
	a := "_" + name
	for m.classScope[a] || m.moduleNames[a] {
		a = "_" + a
	}
	m.aliases[name] = a
	m.moduleNames[a] = true
	return a, true
}

// ann renders a field type annotation and records its imports.
func (m *pyModule) ann(t fieldType) string {
	m.useType(t.Elem)
	prefix := m.g.modelsModule() + "."
	if m.isModels {
		prefix = ""
	}
	a := t.annotation(prefix)
	for _, sub := range rootIdent.FindAllStringSubmatch(a, -1) {
		m.aliasFor(sub[2]) // also builtins such as list/int/str
	}
	return m.ref(a)
}

func (m *pyModule) useType(t *pyType) {
	for _, i := range t.Imports {
		m.addImport(i)
		m.aliasFor(strings.SplitN(i, ".", 2)[0])
	}
	for _, fi := range t.FromImports {
		m.addFrom(fi[0], fi[1])
		m.aliasFor(fi[1])
	}
	if strings.Contains(t.Expr, "{models}") && !m.isModels {
		m.relImports[m.g.modelsModule()] = true
		m.aliasFor(m.g.modelsModule())
	}
}

// annExpr resolves every root identifier of an annotation through the alias
// table (names such as list/int may be shadowed by methods in class scope).
func (m *pyModule) annExpr(a string) string {
	for _, sub := range rootIdent.FindAllStringSubmatch(a, -1) {
		m.aliasFor(sub[2])
	}
	return m.ref(a)
}

// expr references a module-level name (import root, class) through its alias.
func (m *pyModule) expr(s string) string {
	if sub := rootIdent.FindStringSubmatch(s); sub != nil {
		m.aliasFor(sub[2])
	}
	return m.ref(s)
}

func (m *pyModule) header() string {
	var h strings.Builder
	h.WriteString("# Code generated by sqlc. DO NOT EDIT.\n")
	if !m.g.opts.OmitSqlcVersion {
		h.WriteString("# versions:\n")
		fmt.Fprintf(&h, "#   sqlc %s\n", m.g.req.SqlcVersion)
		fmt.Fprintf(&h, "#   sqlc-gen-asyncpg %s\n", Version)
	}
	if m.source != "" {
		fmt.Fprintf(&h, "# source: %s\n", m.source)
	}
	// Names come from the database schema; leading underscores are not a
	// privacy marker here.
	h.WriteString("# pyright: reportPrivateUsage=false, reportUnusedClass=false\n")
	h.WriteString("# ruff: noqa\n")
	return h.String()
}

func (m *pyModule) render() string {
	var out strings.Builder
	out.WriteString(m.header())

	var std, third, localFrom []string
	stdlib := map[string]bool{"datetime": true, "decimal": true, "enum": true, "ipaddress": true, "typing": true, "uuid": true, "contextlib": true, "collections": true, "collections.abc": true}
	for mod := range m.imports {
		root, _, _ := strings.Cut(mod, ".")
		if stdlib[root] || stdlib[mod] {
			std = append(std, "import "+mod)
		} else {
			third = append(third, "import "+mod)
		}
	}
	for mod, names := range m.fromImports {
		var ns []string
		for n := range names {
			ns = append(ns, n)
		}
		sort.Strings(ns)
		line := "from " + mod + " import " + strings.Join(ns, ", ")
		switch {
		case strings.HasPrefix(mod, "."):
			localFrom = append(localFrom, line)
		case stdlib[strings.SplitN(mod, ".", 2)[0]]:
			std = append(std, line)
		default:
			third = append(third, line)
		}
	}
	sort.Strings(std)
	sort.Strings(third)
	sort.Strings(localFrom)
	var local []string
	var rels []string
	for r := range m.relImports {
		rels = append(rels, r)
	}
	sort.Strings(rels)
	if len(rels) > 0 {
		local = append(local, "from . import "+strings.Join(rels, ", "))
	}
	local = append(local, localFrom...)
	var tmods []string
	for mod := range m.typeOnly {
		tmods = append(tmods, mod)
	}
	sort.Strings(tmods)

	groups := [][]string{std, third, local}
	first := true
	for _, grp := range groups {
		if len(grp) == 0 {
			continue
		}
		if first {
			out.WriteString("\n")
			first = false
		} else {
			out.WriteString("\n")
		}
		for _, l := range grp {
			out.WriteString(l)
			out.WriteByte('\n')
		}
	}
	if len(tmods) > 0 {
		out.WriteString("\nif typing.TYPE_CHECKING:\n")
		for _, mod := range tmods {
			var ns []string
			for n := range m.typeOnly[mod] {
				ns = append(ns, n)
			}
			sort.Strings(ns)
			fmt.Fprintf(&out, "    from %s import %s\n", mod, strings.Join(ns, ", "))
		}
	}
	// aliases for imported names (class aliases are emitted inline)
	var aliasLines []string
	for name, a := range m.aliases {
		if m.isLocalClass(name) {
			continue
		}
		aliasLines = append(aliasLines, fmt.Sprintf("%s = %s", a, name))
	}
	sort.Strings(aliasLines)
	if len(aliasLines) > 0 {
		out.WriteString("\n")
		for _, l := range aliasLines {
			out.WriteString(l)
			out.WriteByte('\n')
		}
	}
	if m.needEnumHelper || m.needArrayHelper {
		t := m.expr("typing")
		if m.needEnumHelper {
			fmt.Fprintf(&out, "\n\ndef _sqlc_enum(cls: %[1]s.Any, value: %[1]s.Any) -> %[1]s.Any:\n", t)
			out.WriteString("    return None if value is None else cls(value)\n")
		}
		if m.needArrayHelper {
			fmt.Fprintf(&out, "\n\ndef _sqlc_enum_array(cls: %[1]s.Any, value: %[1]s.Any, dims: int) -> %[1]s.Any:\n", t)
			out.WriteString("    if value is None:\n        return None\n")
			out.WriteString("    if dims == 1:\n        return [None if v is None else cls(v) for v in value]\n")
			out.WriteString("    return [_sqlc_enum_array(cls, v, dims - 1) for v in value]\n")
		}
	}
	body := strings.TrimRight(m.b.String(), "\n")
	if body != "" {
		out.WriteString("\n")
		out.WriteString(body)
		out.WriteString("\n")
	}
	return normalizeBlankLines(out.String())
}

// normalizeBlankLines applies PEP 8 vertical spacing: two blank lines around
// top-level definitions, at most one blank line inside blocks.
func normalizeBlankLines(src string) string {
	lines := strings.Split(strings.TrimRight(src, "\n"), "\n")
	var out []string
	blanks := 0
	prevIndented := false
	prevDecorator := false
	inString := false
	started := false
	for _, l := range lines {
		if inString {
			out = append(out, l)
			if strings.Count(l, `"""`)%2 == 1 {
				inString = false
			}
			continue
		}
		if strings.TrimSpace(l) == "" {
			blanks++
			continue
		}
		indented := strings.HasPrefix(l, " ")
		want := blanks
		switch {
		case !started:
			want = 0
		case !indented:
			isDef := strings.HasPrefix(l, "class ") || strings.HasPrefix(l, "def ") || strings.HasPrefix(l, "async def ") || strings.HasPrefix(l, "@")
			switch {
			case prevDecorator:
				want = 0
			case isDef || prevIndented:
				want = 2
			case want > 2:
				want = 2
			}
		default:
			trim := strings.TrimLeft(l, " ")
			isDef := strings.HasPrefix(trim, "def ") || strings.HasPrefix(trim, "async def ") || strings.HasPrefix(trim, "@")
			switch {
			case prevDecorator:
				want = 0
			case want > 1:
				want = 1
			case isDef && !strings.HasSuffix(out[len(out)-1], ":") && blanks == 0:
				want = 1
			}
		}
		for range want {
			out = append(out, "")
		}
		out = append(out, l)
		started = true
		blanks = 0
		prevIndented = indented
		trim := strings.TrimLeft(l, " ")
		prevDecorator = strings.HasPrefix(trim, "@")
		if strings.Count(l, `"""`)%2 == 1 {
			inString = true
		}
	}
	return strings.Join(out, "\n") + "\n"
}

func (m *pyModule) isLocalClass(name string) bool {
	return m.localClasses()[name]
}

func (m *pyModule) localClasses() map[string]bool {
	if !m.isModels {
		return map[string]bool{}
	}
	out := map[string]bool{}
	for _, e := range m.g.enums {
		out[e.Name] = true
	}
	for _, s := range m.g.models {
		out[s.Name] = true
	}
	return out
}
