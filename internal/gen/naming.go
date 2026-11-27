package gen

import (
	"fmt"
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"

	upstream "github.com/jinzhu/inflection"
)

var pyKeywords = map[string]struct{}{
	"False": {}, "None": {}, "True": {}, "and": {}, "as": {}, "assert": {},
	"async": {}, "await": {}, "break": {}, "class": {}, "continue": {},
	"def": {}, "del": {}, "elif": {}, "else": {}, "except": {}, "finally": {},
	"for": {}, "from": {}, "global": {}, "if": {}, "import": {}, "in": {},
	"is": {}, "lambda": {}, "nonlocal": {}, "not": {}, "or": {}, "pass": {},
	"raise": {}, "return": {}, "try": {}, "while": {}, "with": {}, "yield": {},
}

func isKeyword(s string) bool {
	_, ok := pyKeywords[s]
	return ok
}

func isIdentStart(r rune) bool { return r == '_' || unicode.IsLetter(r) }
func isIdentPart(r rune) bool  { return r == '_' || unicode.IsLetter(r) || unicode.IsDigit(r) }

func isIdentifier(s string) bool {
	if s == "" {
		return false
	}
	for i, r := range s {
		if i == 0 && !isIdentStart(r) {
			return false
		}
		if !isIdentPart(r) {
			return false
		}
	}
	return true
}

// sanitize returns a valid, non-keyword Python identifier.
func sanitize(name string) string {
	out := strings.Map(func(r rune) rune {
		if isIdentPart(r) {
			return r
		}
		return '_'
	}, name)
	if out == "" {
		out = "_"
	}
	r, _ := utf8.DecodeRuneInString(out)
	if unicode.IsDigit(r) {
		out = "_" + out
	}
	// "__x" is name-mangled in class bodies.
	if strings.HasPrefix(out, "__") {
		out = "_" + strings.TrimLeft(out, "_")
		if out == "_" {
			out = "_x"
		}
	}
	if isKeyword(out) {
		out += "_"
	}
	return out
}

// className mirrors sqlc's StructName.
func (g *generator) className(name string) string {
	if r := g.opts.Rename[name]; r != "" {
		return r
	}
	name = strings.Map(func(r rune) rune {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			return r
		}
		return '_'
	}, name)
	var b strings.Builder
	for p := range strings.SplitSeq(name, "_") {
		if _, ok := g.opts.initialisms[p]; ok {
			b.WriteString(strings.ToUpper(p))
		} else {
			b.WriteString(title(p))
		}
	}
	out := b.String()
	if out == "" {
		out = "_"
	}
	r, _ := utf8.DecodeRuneInString(out)
	if unicode.IsDigit(r) {
		out = "_" + out
	}
	if isKeyword(out) {
		out += "_"
	}
	return out
}

// fieldName returns the Python attribute name for a column.
func (g *generator) fieldName(name string) string {
	if r := g.opts.Rename[name]; r != "" {
		return r
	}
	return sanitize(name)
}

func title(s string) string {
	if s == "" {
		return s
	}
	r, n := utf8.DecodeRuneInString(s)
	return string(unicode.ToTitle(r)) + s[n:]
}

// snakeCase: "GetAuthorByID" -> "get_author_by_id".
func snakeCase(s string) string {
	runes := []rune(s)
	var b strings.Builder
	for i := range runes {
		r := runes[i]
		// "IDs", "URLs": plural s stays with the acronym.
		if r == 's' && i >= 2 && unicode.IsUpper(runes[i-1]) && unicode.IsUpper(runes[i-2]) &&
			(i+1 == len(runes) || !unicode.IsLower(runes[i+1])) {
			b.WriteRune(r)
			continue
		}
		if unicode.IsUpper(r) {
			if i > 0 {
				prev := runes[i-1]
				pluralS := i+1 < len(runes) && runes[i+1] == 's' &&
					(i+2 == len(runes) || !unicode.IsLower(runes[i+2])) && unicode.IsUpper(prev)
				nextLower := i+1 < len(runes) && unicode.IsLower(runes[i+1]) && !pluralS
				if prev != '_' && (unicode.IsLower(prev) || unicode.IsDigit(prev) || (unicode.IsUpper(prev) && nextLower)) {
					b.WriteByte('_')
				}
			}
			b.WriteRune(unicode.ToLower(r))
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func upperSnake(s string) string {
	return strings.ToUpper(snakeCase(s))
}

func singular(name string, exclusions []string) string {
	for _, e := range exclusions {
		if strings.EqualFold(name, e) {
			return name
		}
	}
	switch strings.ToLower(name) {
	case "campus", "meta":
		return name
	case "calories":
		return "calorie"
	case "waves":
		return "wave"
	case "metadata":
		return "metadata"
	}
	return upstream.Singular(name)
}

// enumMemberName returns the Python enum member name for a value.
func enumMemberName(v string) string {
	s := strings.Map(func(r rune) rune {
		switch {
		case strings.ContainsRune("-/:_ ", r):
			return '_'
		case r >= 'a' && r <= 'z', r >= 'A' && r <= 'Z', r >= '0' && r <= '9':
			return r
		default:
			return -1
		}
	}, v)
	return strings.ToUpper(s)
}

func validEnumMember(s string) bool {
	if s == "" || !isIdentifier(s) {
		return false
	}
	// enum reserves names starting with "_".
	if strings.HasPrefix(s, "_") {
		return false
	}
	return true
}

var camelPattern = regexp.MustCompile("[^A-Z][A-Z]+")

// jsonName mirrors sqlc's JSONTagName.
func (g *generator) jsonName(name string) string {
	switch g.opts.JSONTagsCaseStyle {
	case "", "none":
		return name
	case "camel":
		var b strings.Builder
		id := "Id"
		if g.opts.JSONTagsIDUppercase {
			id = "ID"
		}
		for i, p := range strings.Split(name, "_") {
			switch {
			case i == 0:
				b.WriteString(p)
			case p == "id":
				b.WriteString(id)
			default:
				b.WriteString(title(p))
			}
		}
		return b.String()
	case "pascal":
		var b strings.Builder
		for p := range strings.SplitSeq(name, "_") {
			if p == "id" {
				b.WriteString("ID")
			} else {
				b.WriteString(title(p))
			}
		}
		return b.String()
	case "snake":
		s := name
		if !strings.ContainsRune(s, '_') {
			s = camelPattern.ReplaceAllStringFunc(s, func(x string) string { return x[:1] + "_" + x[1:] })
		}
		return strings.ToLower(s)
	}
	panic(fmt.Sprintf("unsupported json case style %q", g.opts.JSONTagsCaseStyle))
}

// uniquer hands out unique names.
type uniquer map[string]struct{}

func (u uniquer) take(name string) string {
	if _, ok := u[name]; !ok {
		u[name] = struct{}{}
		return name
	}
	for i := 2; ; i++ {
		c := fmt.Sprintf("%s_%d", name, i)
		if _, ok := u[c]; !ok {
			u[c] = struct{}{}
			return c
		}
	}
}

func (u uniquer) has(name string) bool {
	_, ok := u[name]
	return ok
}

// pyStr renders a Python string literal.
func pyStr(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '\\':
			b.WriteString(`\\`)
		case '"':
			b.WriteString(`\"`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		default:
			switch {
			case r < 0x20 || r == 0x7f:
				fmt.Fprintf(&b, `\x%02x`, r)
			case r == 0x2028 || r == 0x2029 || r == 0xfeff:
				fmt.Fprintf(&b, `\u%04x`, r)
			default:
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}

// pyTripleStr renders a byte-exact triple-quoted Python string literal.
func pyTripleStr(s string) string {
	var b strings.Builder
	b.WriteString(`"""`)
	run := 0
	rs := []rune(s)
	for i, r := range rs {
		if r == '"' {
			run++
			if run == 3 || i == len(rs)-1 {
				b.WriteString(`\"`)
				run = 0
				continue
			}
			b.WriteRune(r)
			continue
		}
		run = 0
		switch r {
		case '\\':
			b.WriteString(`\\`)
		case '\r':
			b.WriteString(`\r`)
		case '\n', '\t':
			b.WriteRune(r)
		default:
			switch {
			case r < 0x20 || r == 0x7f: // includes \f and \v
				fmt.Fprintf(&b, `\x%02x`, r)
			case r == 0x2028 || r == 0x2029 || r == 0xfeff:
				fmt.Fprintf(&b, `\u%04x`, r)
			default:
				b.WriteRune(r)
			}
		}
	}
	b.WriteString(`"""`)
	return b.String()
}
