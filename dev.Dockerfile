# This a dev image for testing your plugin when installed into the adl image
FROM adl:latest AS base

FROM adl:latest

USER root

ARG PLUGIN_BUILD_UID
ENV PLUGIN_BUILD_UID=${PLUGIN_BUILD_UID:-9999}
ARG PLUGIN_BUILD_GID
ENV PLUGIN_BUILD_GID=${PLUGIN_BUILD_GID:-9999}

# If we aren't building as the same user that owns all the files in the base
# image/installed plugins we need to chown everything first.
COPY --from=base --chown=$PLUGIN_BUILD_UID:$PLUGIN_BUILD_GID /adl /adl
RUN usermod -u $PLUGIN_BUILD_UID $DOCKER_USER

# Install your dev dependencies manually.
COPY --chown=$PLUGIN_BUILD_UID:$PLUGIN_BUILD_GID ./plugins/adl_weatherlink_plugin/requirements/dev.txt /tmp/plugin-dev-requirements.txt
RUN . /adl/venv/bin/activate && pip3 install -r /tmp/plugin-dev-requirements.txt

COPY --chown=$PLUGIN_BUILD_UID:$PLUGIN_BUILD_GID ./plugins/adl_weatherlink_plugin/ $ADL_PLUGIN_DIR/adl_weatherlink_plugin/
RUN . /adl/venv/bin/activate && /adl/plugins/install_plugin.sh --folder $ADL_PLUGIN_DIR/adl_weatherlink_plugin --dev

USER $PLUGIN_BUILD_UID:$PLUGIN_BUILD_GID
ENV DJANGO_SETTINGS_MODULE='adl.config.settings.dev'
CMD ["django-dev"]