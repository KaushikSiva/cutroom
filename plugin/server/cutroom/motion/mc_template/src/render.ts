import project from './project?project';
import {Renderer, Vector2} from '@motion-canvas/core';
import {CaptureExporter} from './capture';

// the vite plugin replaces makeProject's plugin list, so register the capture exporter directly
(project as any).meta.rendering.exporter.exporters.push(CaptureExporter);

(window as any).__cutroomRender = async (o: {w: number; h: number; fps: number; transparent: boolean}) => {
  (project as any).logger.onLogged.subscribe((p: any) => console.log('[mc]', p.level, p.message, p.stack ?? ''));
  const renderer = new Renderer(project as any);
  let result: any = null;
  renderer.onFinished.subscribe(r => (result = r));
  await renderer.render({
    name: 'cutroom',
    range: [0, Infinity],
    fps: o.fps,
    size: new Vector2(o.w, o.h),
    resolutionScale: 1,
    colorSpace: 'srgb',
    background: o.transparent ? null : '#0b0d10',
    exporter: {name: 'cutroom-capture', options: {}},
  } as any);
  return result;
};
(window as any).__cutroomReady = true;
