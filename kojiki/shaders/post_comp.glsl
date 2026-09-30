#version 300 es
precision highp float;
uniform sampler2D uScene, uBloom;
uniform vec2 uOut;
uniform float uBar, uT, uFade, uFlash, uSlash, uBloomK;
out vec4 o;

vec3 aces(vec3 x){ // Narkowicz fit
  return clamp((x*(2.51*x+0.03))/(x*(2.43*x+0.59)+0.14), 0., 1.);
}
float h12(vec2 p){ vec3 p3=fract(vec3(p.xyx)*.1031); p3+=dot(p3,p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }

vec3 sampleScene(vec2 uv){
  // radial chromatic aberration
  vec2 c = uv - .5;
  float k = 0.0035 * dot(c,c) * 4.;
  vec3 col;
  col.r = texture(uScene, uv - c*k).r;
  col.g = texture(uScene, uv).g;
  col.b = texture(uScene, uv + c*k).b;
  vec3 b;
  b.r = texture(uBloom, uv - c*k*2.).r;
  b.g = texture(uBloom, uv).g;
  b.b = texture(uBloom, uv + c*k*2.).b;
  return col + b * uBloomK;
}

void main(){
  vec2 fc = gl_FragCoord.xy;
  float activeH = uOut.y - 2.*uBar;
  if(fc.y < uBar || fc.y > uOut.y - uBar){ o = vec4(0,0,0,1); return; }
  vec2 uv = vec2(fc.x/uOut.x, (fc.y-uBar)/activeH);
  vec2 asp = vec2(uOut.x/activeH, 1.);

  // ---- the sword slash: a diagonal cut, then the frame splits along it
  float lineGlow = 0.;
  if(uSlash > 0.){
    vec2 p0 = vec2(.5,.5);
    vec2 dir = normalize(vec2(1., -.42));
    vec2 nrm = vec2(-dir.y, dir.x);
    vec2 q = (uv - p0)*asp;
    float s = dot(q, nrm);
    float along = dot(q, dir);
    float draw = smoothstep(0., .18, uSlash);                  // blade travels across
    float reach = mix(-1.4, 1.4, draw);
    float onLine = step(along, reach);
    float split = smoothstep(.2, 1., uSlash);
    float sep = split*split*0.05;
    uv -= (dir*sign(s)*sep*0.8 + nrm*sign(s)*sep*0.35)/asp;
    float w = 0.0018 + 0.02*split;
    lineGlow = onLine * (exp(-abs(s)/w)*3. + exp(-abs(s)/(w*8.))*0.6) * (1. - smoothstep(.85,1.,uSlash)*0.3);
    lineGlow += onLine * exp(-abs(s)*abs(s)/0.00002) * 8. * (1.-split);
    // spark at the blade tip
    lineGlow += exp(-length(q - dir*reach)*18.) * 4. * (1.-draw*draw);
  }

  vec3 col = sampleScene(uv);
  col += vec3(.85,.92,1.)*lineGlow;

  // exposure & tonemap
  col *= 1.05;
  col = aces(col);
  // subtle split-tone: cool shadows, warm highlights
  float lum = dot(col, vec3(.2126,.7152,.0722));
  col = mix(col, col*vec3(.92,.98,1.08), (1.-lum)*.25);
  col = pow(col, vec3(1./2.2));

  // vignette
  vec2 vq = (uv-.5)*asp;
  col *= 1. - 0.28*smoothstep(.4, 1.25, length(vq*vec2(.75,1.)));

  // flash & fade
  col = mix(col, vec3(1.,.985,.95), uFlash);
  col *= 1.-uFade;

  // film grain (luminance-weighted)
  float g = h12(fc + fract(uT*24.37)*vec2(113.1, 71.7)) + h12(fc*1.37 + fract(uT*13.1)*vec2(37.3, 91.9)) - 1.;
  col += g * 0.028 * (1. - lum*0.6);
  o = vec4(col, 1.);
}
