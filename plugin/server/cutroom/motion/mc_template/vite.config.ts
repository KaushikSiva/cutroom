import {defineConfig} from 'vite';
import motionCanvas from '@motion-canvas/vite-plugin';

export default defineConfig({
  plugins: [((motionCanvas as any).default ?? motionCanvas)({project: './src/project.ts'})],
  server: {port: Number(process.env.MC_PORT || 9123), strictPort: true},
});
