#version 300 es
precision highp float;
precision highp sampler3D;
uniform float uT;          // global time (s)
uniform float uL;          // scene-local time (s)
uniform vec2  uRes;
uniform sampler3D uN;      // 128^3 tileable smooth value noise, period 32
uniform float uBeat;       // dance-drum envelope (Iwato)
uniform float uShake;      // camera shake amount
out vec4 fragColor;

#define PI  3.14159265359
#define TAU 6.28318530718
#define sat(x) clamp(x, 0., 1.)

float n3(vec3 p){ return texture(uN, p*(1./32.)).r; }
float n2(vec2 p){ return texture(uN, vec3(p*(1./32.), .37)).r; }
float fbm3(vec3 p, int oct){
  float s = 0., a = .5, w = 0.;
  for(int i=0;i<oct;i++){ s += a*n3(p); w += a; p = p*2.03 + vec3(3.1,1.7,5.3); a *= .5; }
  return s/w;
}
float fbm2(vec2 p, int oct){
  float s = 0., a = .5, w = 0.;
  for(int i=0;i<oct;i++){ s += a*n2(p); w += a; p = mat2(1.6,1.2,-1.2,1.6)*p + vec2(3.1,1.7); a *= .5; }
  return s/w;
}
// contrast-stretched noise (texture noise sits around .5 with low variance)
float cn(float x){ return sat((x-.5)*1.9+.5); }

float h11(float p){ p = fract(p*.1031); p *= p+33.33; p *= p+p; return fract(p); }
float h21(vec2 p){ vec3 p3 = fract(vec3(p.xyx)*.1031); p3 += dot(p3, p3.yzx+33.33); return fract((p3.x+p3.y)*p3.z); }
vec2  h22(vec2 p){ vec3 p3 = fract(vec3(p.xyx)*vec3(.1031,.1030,.0973)); p3 += dot(p3, p3.yzx+33.33); return fract((p3.xx+p3.yz)*p3.zy); }
vec3  h33(vec3 p){ p = fract(p*vec3(.1031,.1030,.0973)); p += dot(p, p.yxz+33.33); return fract((p.xxy+p.yxx)*p.zyx); }

mat2 rot(float a){ float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
vec2 getUV(){ return (gl_FragCoord.xy - .5*uRes)/uRes.y; }

// camera basis: columns = right, up, forward
mat3 lookAt(vec3 ro, vec3 ta, float roll){
  vec3 f = normalize(ta-ro);
  vec3 up = vec3(sin(roll), cos(roll), 0.);
  vec3 r = normalize(cross(up, f));
  vec3 u = cross(f, r);
  return mat3(r, u, f);
}
// project a world point to screen uv (same convention as getUV)
vec2 project(vec3 p, vec3 ro, mat3 cam, float zoom){
  vec3 v = p - ro;
  vec3 c = vec3(dot(v,cam[0]), dot(v,cam[1]), dot(v,cam[2]));
  return c.xy/c.z*zoom;
}
vec3 shakeOffset(float amt, float t){
  return amt*vec3(n3(vec3(t*18.,0.,0.))-.5, n3(vec3(0.,t*18.,5.))-.5, 0.)*0.35;
}

float sdBox(vec3 p, vec3 b){ vec3 q = abs(p)-b; return length(max(q,0.)) + min(max(q.x,max(q.y,q.z)),0.); }
float sdRoundBox(vec3 p, vec3 b, float r){ vec3 q = abs(p)-b; return length(max(q,0.)) + min(max(q.x,max(q.y,q.z)),0.) - r; }
float sdEllipsoid(vec3 p, vec3 r){ float k0 = length(p/r); float k1 = length(p/(r*r)); return k0*(k0-1.)/k1; }
float sdCapsule(vec3 p, vec3 a, vec3 b, float r){ vec3 pa=p-a, ba=b-a; float h=sat(dot(pa,ba)/dot(ba,ba)); return length(pa-ba*h)-r; }
float smin(float a, float b, float k){ float h = sat(.5+.5*(b-a)/k); return mix(b,a,h) - k*h*(1.-h); }

// closest approach between a ray and a segment; returns distance, writes ray t and segment param h
float raySeg(vec3 ro, vec3 rd, vec3 a, vec3 b, out float tr, out float hs){
  vec3 ba = b-a, oa = ro-a;
  float a1 = dot(rd,ba), a2 = dot(ba,ba), b1 = dot(rd,oa), b2 = dot(ba,oa);
  float den = a2 - a1*a1;
  hs = sat((b2 - b1*a1)/max(den,1e-6)); // approx: param on segment
  vec3 pb = a + ba*hs;
  tr = max(dot(pb-ro, rd), 0.);
  return length(ro + rd*tr - pb);
}

// soft bokeh-dust / sparkle layer in screen space
vec3 dustLayer(vec2 uv, float t, float scale, float speed, vec3 tint, float seed){
  vec3 acc = vec3(0);
  vec2 p = uv*scale + vec2(seed*13.1, -t*speed);
  vec2 id = floor(p), f = fract(p) - .5;
  for(int j=-1;j<=1;j++) for(int i=-1;i<=1;i++){
    vec2 o = vec2(i,j);
    vec2 r = h22(id+o+seed);
    vec2 c = o + (r-.5)*.8 + .1*vec2(sin(t*.7+r.x*6.), cos(t*.5+r.y*6.));
    float d = length(f - c);
    float sz = .02 + .06*r.x*r.x;
    float tw = .5+.5*sin(t*(1.5+r.y*3.)+r.x*20.);
    acc += tint * smoothstep(sz, sz*.2, d) * (0.3+tw) * step(.55, h21(id+o+seed*7.));
  }
  return acc;
}
