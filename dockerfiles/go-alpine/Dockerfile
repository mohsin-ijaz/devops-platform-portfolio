FROM alpine:latest

WORKDIR /
ADD consumer-gateway /
ADD config.yaml /
ADD config-dev.yaml /
#ADD resource/* /
ADD resource/rbac_model.conf /resource
#ADD config-local.yaml /
ENTRYPOINT ["/consumer-gateway"]