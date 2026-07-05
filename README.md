# brightsky.dev-prometheus
exports weather from brightsky.dev

```yaml
services:
  brightsky-dev:
    image: ghcr.io/knrdl/brightsky.dev-prometheus:edge
    restart: always
    environment:
      lon: '13.5'
      lat: '52.5'
    mem_limit: 100m
    ports:
      - 8080:8080
```