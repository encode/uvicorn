FROM nginx:alpine
# nginx:1.19.1-alpine

COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV SCHEME="http"
ENV LISTEN_PORT="9000"
ENV SOCKET_PATH="/socket/socket.sock"
