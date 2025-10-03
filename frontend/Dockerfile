# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app
COPY . .

# 占位：启动一个简单的 HTTP 服务
RUN npm install -g serve

CMD ["serve", "-s", ".", "-l", "3000"]

