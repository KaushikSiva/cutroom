import {makeProject} from '@motion-canvas/core';
import main from './scenes/main?scene';
import capture from './capture';

export default makeProject({scenes: [main], plugins: [capture]});
