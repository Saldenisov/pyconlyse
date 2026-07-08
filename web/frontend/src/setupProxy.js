const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function setupProxy(app) {
  const backendProxy = createProxyMiddleware({
    target: 'http://localhost:5000',
    changeOrigin: true,
    ws: true,
  });

  app.use('/api', backendProxy);
  app.use('/socket.io', backendProxy);
};
