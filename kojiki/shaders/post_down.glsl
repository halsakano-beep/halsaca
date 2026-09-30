#version 300 es
precision highp float;
uniform sampler2D uSrc;
uniform vec2 uTexel;
uniform vec2 uDst;   // 1/destination size
uniform int uFirst;
out vec4 o;
// 13-tap downsample (Jimenez 2014) with a soft-knee bright pass on the first level
vec3 S(vec2 uv){ return texture(uSrc, uv).rgb; }
void main(){
  vec2 uv = gl_FragCoord.xy * uDst;
  vec2 d = uTexel;
  vec3 a=S(uv+d*vec2(-2,2)), b=S(uv+d*vec2(0,2)), c=S(uv+d*vec2(2,2));
  vec3 e=S(uv+d*vec2(-2,0)), f=S(uv), g=S(uv+d*vec2(2,0));
  vec3 h=S(uv+d*vec2(-2,-2)), i=S(uv+d*vec2(0,-2)), j=S(uv+d*vec2(2,-2));
  vec3 k=S(uv+d*vec2(-1,1)), l=S(uv+d*vec2(1,1)), m=S(uv+d*vec2(-1,-1)), n=S(uv+d*vec2(1,-1));
  vec3 col = f*0.125 + (a+c+h+j)*0.03125 + (b+e+g+i)*0.0625 + (k+l+m+n)*0.125;
  if(uFirst==1){
    float br = max(col.r, max(col.g, col.b));
    float th = 0.85, knee = 0.6;
    float soft = clamp(br - th + knee, 0., 2.*knee); soft = soft*soft/(4.*knee+1e-4);
    float w = max(soft, br - th) / max(br, 1e-4);
    col *= w;
    col = min(col, vec3(60.)); // tame fireflies
  }
  o = vec4(col, 1.);
}
