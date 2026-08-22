package main

import (
	"log"

	httpapi "roxy-gateway/internal/http"
)

func main() {
	r := httpapi.NewRouter()
	if err := r.Run(":8080"); err != nil {
		log.Fatal(err)
	}
}
