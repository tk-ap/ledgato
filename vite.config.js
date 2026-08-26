import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  plugins: [
    {
      name: "ledgato-app-route",
      configureServer(server) {
        server.middlewares.use((request, _response, next) => {
          if (request.url === "/app") request.url = "/app/";
          next();
        });
      },
    },
  ],
  build: {
    rollupOptions: {
      input: {
        landing: resolve(import.meta.dirname, "index.html"),
        app: resolve(import.meta.dirname, "app/index.html"),
      },
    },
  },
});
