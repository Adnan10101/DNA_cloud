#!/bin/bash

echo "Starting image build process......"

echo "Enter Version....."
read DOCKER_IMAGE_TAG
DOCKER_IMAGE_NAME="automount-pv-pvc-link"
DEPLOYMENT_NAME="pv-pvc-link"
DOCKER_REGISTRY="adnan10101"
DOCKERFILE_REPO="/home/dna1pe3/projects/auto_mount_services/PVC_watch"

echo "Building docker image......."
sudo docker build --no-cache -t $DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG $DOCKERFILE_REPO

echo "Tagging and pushing to dockerhub......"
sudo docker tag $DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG adnan10101/automount-pv-pvc-link:$DOCKER_IMAGE_TAG
sudo docker push $DOCKER_REGISTRY/$DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG

echo "Checking if pv-pvc-link deployment exists....."
if kubectl get deployment $DEPLOYMENT_NAME > /dev/null 2>&1; then
    echo "Deployment exists........"
    kubectl delete deployment $DEPLOYMENT_NAME
    if [ $? -ne 0 ]; then
        echo "Failed to delete deployment. Exiting."
        exit 1
    fi
else
    echo "Deployment does not exist....."
fi

