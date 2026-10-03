// A Motion Canvas exporter that hands every rendered frame to the page owner (Playwright) instead of the editor.
import {ObjectMetaField, makePlugin} from '@motion-canvas/core';
import type {Exporter, Project, RendererSettings} from '@motion-canvas/core';

export class CaptureExporter implements Exporter {
  public static readonly id = 'cutroom-capture';
  public static readonly displayName = 'Cutroom capture';
  public static meta() {
    return new ObjectMetaField(this.name, {});
  }
  public static async create(_project: Project, _settings: RendererSettings) {
    return new CaptureExporter();
  }
  public async handleFrame(canvas: HTMLCanvasElement, frame: number) {
    const url = canvas.toDataURL('image/png');
    await (window as any).__cutroomFrame(frame, url);
  }
}

export default makePlugin({
  name: 'cutroom-capture',
  exporters() {
    return [CaptureExporter as any];
  },
});
