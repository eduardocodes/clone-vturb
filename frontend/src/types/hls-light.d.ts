// hls.js publica o build light em "hls.js/light" sem declaração própria; a API é a mesma
declare module 'hls.js/light' {
  export { default } from 'hls.js'
}
