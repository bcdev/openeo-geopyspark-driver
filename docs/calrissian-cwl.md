# CWL based openEO processing using Calrissian

This document describes how CWL based processing is implemented
in the openEO GeoPySpark driver when running on a Kubernetes cluster.

## Background and terminology

[CWL (Common Workflow Language)](https://www.commonwl.org) is an open standard
for describing how to run (command line) tools and connect them to create workflows.
While CWL and openEO are a bit competing due to this conceptual overlap,
there is demand to run existing or new CWL workflows as part of a larger openEO processing chain.
This is comparable to UDFs which allow to run (Python) scripts as part of an openEO workflow.

[Calrissian](https://duke-gcb.github.io/calrissian/) is a CWL implementation
designed to run inside a Kubernetes cluster.


## Kubernetes setup

If running on minikube, first run this:

```bash
minikube delete # clean up previous sessions
minikube start
NAMESPACE_NAME=calrissian-demo-project
kubectl create namespace "$NAMESPACE_NAME"
helm install csi-s3 yandex-s3/csi-s3 -n calrissian-demo-project
kubectl apply -f docs/calrissian-local-minio.yaml
kubectl wait -n calrissian-demo-project --for=condition=available --timeout=300s deployment/minio
AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin aws --endpoint-url http://$(minikube ip):30000 s3 mb s3://calrissian
AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin aws --endpoint-url http://$(minikube ip):30000 s3api put-bucket-policy --bucket calrissian --policy '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::calrissian/*"
    }
  ]
}'
open http://$(minikube ip):30001
minikube dashboard
```

Note: this is an extension to the Kubernetes setup discussed
in the [Calrissian cluster configuration docs](https://duke-gcb.github.io/calrissian/cluster-configuration/).

```bash
# Create a namespace for the Calrissian service:

NAMESPACE_NAME=calrissian-demo-project
kubectl create namespace "$NAMESPACE_NAME"

# Roles and permissions
kubectl \
    --namespace="$NAMESPACE_NAME" \
    create role \
    pod-manager-role \
    --verb=create,patch,delete,list,watch \
    --resource=pods

kubectl \
    --namespace="$NAMESPACE_NAME" \
    create role \
    log-reader-role \
    --verb=get,list \
    --resource=pods/log

kubectl \
    --namespace="$NAMESPACE_NAME" \
    create role \
    job-manager-role \
    --verb=create,list,get,delete \
    --resource=jobs

kubectl \
    --namespace="$NAMESPACE_NAME" \
    create role \
    pvc-reader-role \
    --verb=list,get \
    --resource=persistentvolumeclaims


# And attach roles to the service account in that namespace:

kubectl \
    --namespace="$NAMESPACE_NAME" \
    create rolebinding \
    pod-manager-default-binding \
    --role=pod-manager-role \
    --serviceaccount=${NAMESPACE_NAME}:default

kubectl \
    --namespace="$NAMESPACE_NAME" \
    create rolebinding \
    log-reader-default-binding \
    --role=log-reader-role \
    --serviceaccount=${NAMESPACE_NAME}:default


# Also attach roles to the appropriate service accounts (in other namespaces)

ENV=dev
# ENV=staging
# ENV=prod
OTHER_NAMESPACE_NAME=spark-jobs-$ENV

for SERVICE_ACCOUNT_NAME in openeo batch-jobs
do
    kubectl \
        --namespace="$NAMESPACE_NAME" \
        create rolebinding \
        job-manager-${OTHER_NAMESPACE_NAME}-${SERVICE_ACCOUNT_NAME} \
        --role=job-manager-role \
        --serviceaccount=${OTHER_NAMESPACE_NAME}:${SERVICE_ACCOUNT_NAME}

    kubectl \
        --namespace="$NAMESPACE_NAME" \
        create rolebinding \
        pvc-reader-${OTHER_NAMESPACE_NAME}-${SERVICE_ACCOUNT_NAME} \
        --role=pvc-reader-role \
        --serviceaccount=${OTHER_NAMESPACE_NAME}:${SERVICE_ACCOUNT_NAME}
done

# Create a `StorageClass` `csi-s3-calrissian` for the volumes used by Calrissian.
# For example with `geesefs` from `ru.yandex.s3.csi`:
cat <<EOF | kubectl create -f -
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: csi-s3-calrissian
provisioner: ru.yandex.s3.csi
volumeBindingMode: Immediate
parameters:
  mounter: geesefs
  # you can set mount options here, for example limit memory cache size (recommended)
  options: "--memory-limit 1000 --dir-mode 0777 --file-mode 0666 --no-systemd --fsync-on-close --stat-cache-ttl 0"
  # to use an existing bucket, specify it here:
  bucket: calrissian
  csi.storage.k8s.io/provisioner-secret-name: csi-s3-secret
  csi.storage.k8s.io/provisioner-secret-namespace: csi-s3
  csi.storage.k8s.io/controller-publish-secret-name: csi-s3-secret
  csi.storage.k8s.io/controller-publish-secret-namespace: csi-s3
  csi.storage.k8s.io/node-stage-secret-name: csi-s3-secret
  csi.storage.k8s.io/node-stage-secret-namespace: csi-s3
  csi.storage.k8s.io/node-publish-secret-name: csi-s3-secret
  csi.storage.k8s.io/node-publish-secret-namespace: csi-s3
EOF


# For storage, create the `PersistentVolumeClaim`s for the input, tmp and output volumes.

cat <<EOF | kubectl create -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: calrissian-input-data
  namespace: calrissian-demo-project
spec:
  accessModes:
    - ReadWriteOnce
    - ReadOnlyMany
  resources:
    requests:
      storage: 1Gi
  storageClassName: csi-s3-calrissian
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: calrissian-tmpout
  namespace: calrissian-demo-project
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 1Gi
  storageClassName: csi-s3-calrissian
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: calrissian-output-data
  namespace: calrissian-demo-project
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 1Gi
  storageClassName: csi-s3-calrissian
EOF

```


## Further openeo-geopyspark-driver configuration

Further configuration of the openeo-geopyspark-driver application
is done through the `calrissian_config` field of `GpsBackendConfig`
(also see the general [configuration docs](./configuration.md)).
This field expects (unless no Calrissian integration is necessary) a
`CalrissianConfig` sub-configuration object
(defined at `openeogeotrellis.config.integrations.calrissian_config`),
which allows to configure various aspects of the Calrissian integration.
