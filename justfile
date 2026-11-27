sqlc_src := env("SQLC_SRC", "/tmp/sqlc-src")
sqlc_version := "v1.31.1"
pythons := "3.13,3.14,3.15"

default: test

build:
    go build -o bin/sqlc-gen-asyncpg .

wasm:
    GOOS=wasip1 GOARCH=wasm go build -trimpath -o bin/sqlc-gen-asyncpg.wasm .
    shasum -a 256 bin/sqlc-gen-asyncpg.wasm

tidy:
    go mod tidy -diff

vet:
    go vet ./...

lint:
    golangci-lint run ./...

vuln:
    go run golang.org/x/vuln/cmd/govulncheck@latest ./...

modernize:
    go run golang.org/x/tools/go/analysis/passes/modernize/cmd/modernize@latest -test ./...
    go fix -diff ./...

unit:
    go test -race ./...

check: tidy vet lint vuln modernize build wasm unit

postgres:
    docker start sqlcpy-pg 2>/dev/null || docker run -d --name sqlcpy-pg -e POSTGRES_PASSWORD=postgres -p 55439:5432 pgvector/pgvector:pg18
    until docker exec sqlcpy-pg pg_isready -U postgres >/dev/null 2>&1; do sleep 0.5; done

e2e: postgres
    cd e2e && python3 run.py --pythons {{pythons}}

corpus: postgres
    [ -d {{sqlc_src}} ] || git clone --depth 1 --branch {{sqlc_version}} https://github.com/sqlc-dev/sqlc.git {{sqlc_src}}
    cd e2e && python3 corpus.py --sqlc-src {{sqlc_src}}

test: check e2e corpus

# bump internal/gen/render.go Version, commit, then: just release v0.1.0
release version:
    @grep -q 'const Version = "{{version}}"' internal/gen/render.go || (echo "internal/gen/render.go Version is not {{version}}" && exit 1)
    @git diff --quiet HEAD || (echo "working tree is dirty" && exit 1)
    git tag {{version}}
    git push origin {{version}}

clean:
    rm -rf bin e2e/.corpus e2e/cases/*/sqlc.generated.json
