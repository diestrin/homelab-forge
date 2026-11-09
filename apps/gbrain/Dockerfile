# GBrain MCP server image (ADR-017). Build context: apps/gbrain.
# GBrain is NOT on npm: install only from GitHub. Pin GBRAIN_REF to a tag or
# commit for reproducible builds; `stable` is upstream's soaked channel.
FROM oven/bun:1.4-debian
ARG GBRAIN_REF=stable
ENV BUN_INSTALL=/usr/local/bun \
    PATH=/usr/local/bun/bin:$PATH \
    GBRAIN_HOME=/data
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && bun install -g "github:garrytan/gbrain#${GBRAIN_REF}" \
    && gbrain --version
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && mkdir -p /data && chown -R bun:bun /data
USER bun
EXPOSE 3131
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
