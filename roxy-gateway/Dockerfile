# syntax=docker/dockerfile:1
FROM golang:1.24-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/roxy ./cmd/roxy
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/seed ./cmd/seed

FROM alpine:3.21
RUN apk add --no-cache ca-certificates
WORKDIR /app
COPY --from=build /out/roxy /app/roxy
COPY --from=build /out/seed /app/seed
EXPOSE 8080
USER nobody
CMD ["/app/roxy"]
