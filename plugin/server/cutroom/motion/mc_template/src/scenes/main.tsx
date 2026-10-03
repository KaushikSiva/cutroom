import {makeScene2D, Circle, Txt} from '@motion-canvas/2d';
import {createRef, all, waitFor} from '@motion-canvas/core';
export default makeScene2D(function* (view) {
  const c = createRef<Circle>();
  view.add(<Circle ref={c} size={200} fill={'#e8b04a'} />);
  view.add(<Txt text={'Motion Canvas'} y={220} fontSize={64} fill={'#f3efe6'} />);
  yield* all(c().scale(1.6, 1).to(1, 1));
  yield* waitFor(0.5);
});
