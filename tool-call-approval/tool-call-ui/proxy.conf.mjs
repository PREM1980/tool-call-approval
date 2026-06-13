export default {
  '/api': {
    target: process.env.API_TARGET || 'http://127.0.0.1:8080',
    changeOrigin: true,
    secure: false,
    headers: { Connection: 'keep-alive' },
  },
};
