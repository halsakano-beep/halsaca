#version 300 es
precision highp float;
uniform sampler2D uSrc;   // smaller level
uniform vec2 uTexel;
uniform vec2 uDst;   // 1/destination size      // texel of the smaller level
out vec4 o;
// 9-tap tent upsample, additively blended into the next larger level
void main(){
  vec2 uv = gl_FragCoord.xy * uDst;
  vec2 d = uTexel * 1.0;
  vec3 c = texture(uSrc, uv).rgb*4.;
  c += (texture(uSrc, uv+vec2(d.x,0)).rgb + texture(uSrc, uv-vec2(d.x,0)).rgb + texture(uSrc, uv+vec2(0,d.y)).rgb + texture(uSrc, uv-vec2(0,d.y)).rgb)*2.;
  c += texture(uSrc, uv+d).rgb + texture(uSrc, uv-d).rgb + texture(uSrc, uv+vec2(d.x,-d.y)).rgb + texture(uSrc, uv+vec2(-d.x,d.y)).rgb;
  o = vec4(c/16., 1.);
}
