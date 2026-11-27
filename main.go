package main

import (
	"github.com/sqlc-dev/plugin-sdk-go/codegen"

	"github.com/zachnoble/sqlc-gen-asyncpg/internal/gen"
)

func main() {
	codegen.Run(gen.Generate)
}
