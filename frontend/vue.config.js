const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8003', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8003', ws: true, changeOrigin: true },
      '/uploads': { target: 'http://127.0.0.1:8003', changeOrigin: true },
    },
    client: {
      overlay: false,
    },
  },
})
