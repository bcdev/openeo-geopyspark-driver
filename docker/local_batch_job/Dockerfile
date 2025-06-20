# The base image is buiild from vito CI/CD pipeline:
FROM vito-docker.artifactory.vgt.vito.be/openeo-base:latest
# docker build -t openeo_docker_local . -f docker/local_batch_job/Dockerfile

USER root

# from openeo-deploy/mep/entrypont.sh
ENV PYTHON_EGG_CACHE=./
ENV PATH="/opt/venv/bin:$PATH"
ENV WMTS_BASE_URL_PATTERN=http://openeo.vgt.vito.be/openeo/services/%s

# from jenkinslib/resources/python/test.sh
ENV PYTHONPATH="$SPARK_HOME/python:$PYTHONPATH"
ENV PYTHONPATH="$SPARK_HOME/python/lib/py4j-0.10.9.7-src.zip:$PYTHONPATH"

# test python packages:
RUN $PYSPARK_PYTHON -c "import pyspark;import openeo;import otbApplication"

# COPY files to allow building the image with the latest version stored locally:
# TODO: Disable this by default when a new openeo-base is available.
COPY ./openeogeotrellis /opt/venv/lib64/python3.8/site-packages/openeogeotrellis

# to find jars:
ENV GEOPYSPARK_JARS_PATH=/opt/

# for logging:
ENV OPENEO_BATCH_JOB_ID="unknown-job"
ENV OPENEO_USER_ID="openeo_docker_local"
# When debugging is enabled, port 4040 and 5009 are exposed:
ENV OPENEO_LOCAL_DEBUGGING="false"
# Avoid GDAL making .aux files
ENV GDAL_PAM_ENABLED=NO

# Write directly to the mount. If an error occurs, there is something to debug with
# openeo.log will be written in the current directory, so change current directory
RUN mkdir /opt/docker_mount
WORKDIR /opt/docker_mount
# Can't use run_graph_locally.py directly, because it refers to a non-existing Python installation
ENTRYPOINT  ${PYSPARK_PYTHON} -u /opt/venv/bin/run_graph_locally.py $0 $@
