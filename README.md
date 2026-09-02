# ADL WeatherLink Plugin

Collects observation data from **Davis Instruments** weather stations through
the **WeatherLink v2 REST API** into an [ADL](https://github.com/wmo-raf/adl)
instance. On each collection cycle ADL reads each linked station's current
conditions and stores the sensor fields you have mapped against your ADL
stations and data parameters.

**Operator guide:** [docs/guide.md](docs/guide.md) — prerequisites,
installation, every connection and station-link field, the sensor/parameter
selectors, collection behaviour, diagnostics and troubleshooting. The guide
is also published on the central ADL documentation site.

## Development setup

The plugin runs inside the ADL core image. Build the `adl:latest` image from
the [ADL core repository](https://github.com/wmo-raf/adl) first, then:

```bash
git clone https://github.com/wmo-raf/adl-weatherlink-plugin.git
cd adl-weatherlink-plugin
cp .env.sample .env        # set PLUGIN_BUILD_UID=$(id -u), PLUGIN_BUILD_GID=$(id -g), ADL_DB_PASSWORD
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up
docker compose -f docker-compose.dev.yml exec adl adl createsuperuser
```

The admin is served by the bundled nginx proxy on `ADL_WEB_PROXY_PORT`
(default 80). The plugin source is bind-mounted, so code changes reload the
dev server. If the build fails with `pull access denied` for `adl:latest`,
prefix the build with `DOCKER_BUILDKIT=0`.

Lint and format from `plugins/adl_weatherlink_plugin/` with `make lint` and
`make format`. See [CONTRIBUTING.md](CONTRIBUTING.md) — a change to any
connection or station-link field must update the guide in the same PR.
