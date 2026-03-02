FROM gocv/opencv:4.8.0 as builder
WORKDIR /app
COPY go.mod ./
RUN go mod download
COPY . .
RUN go mod tidy
RUN CGO_ENABLED=1 GOOS=linux go build -o ingestion main.go

FROM gocv/opencv:4.8.0
WORKDIR /app
COPY --from=builder /app/ingestion /app/ingestion
EXPOSE 8081
ENTRYPOINT ["/app/ingestion"]