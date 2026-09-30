// ============ S5: 夜明け — dawn through the sea torii ============
// local time 0..19 ; crow 2.5..9.5 ; title 6.0

float L;
vec3 sunD;
const float TZ = 26.;

// ---- torii (2D profile, x/y in world units, used for mask and 3D)
float kasagiY(float ax){ return 8.35 + .42*pow(sat(ax/5.9), 2.6); }
float torii2D(vec2 p){
  float ax = abs(p.x);
  float pil = max(abs(ax - 3.25 + p.y*.025) - (.44 - p.y*.012), p.y - 8.2);
  float ky = kasagiY(ax);
  float kas = max(abs(p.y - ky) - .3, ax - 5.9 + (p.y - ky)*.4);
  float shi = max(abs(p.y - (ky - .55)) - .2, ax - 5.2);
  float nuk = max(abs(p.y - 6.55) - .24, ax - 4.55);
  float gak = max(abs(p.y - 7.35) - .55, ax - .42);
  return min(min(pil, kas), min(min(shi, nuk), gak));
}
float torii(vec3 p){
  vec3 q = p - vec3(0., 0., TZ);
  float ax = abs(q.x);
  // round pillars
  float pil = max(length(vec2(ax - 3.25 + q.y*.025, q.z)) - (.44 - q.y*.012), q.y - 8.2);
  float ky = kasagiY(ax);
  float kas = sdBox(vec3(ax - 2.95, q.y - ky, q.z), vec3(2.95, .3, .62))*.8;
  kas = max(kas, ax - 5.9 + (q.y - ky)*.4);
  float shi = sdBox(vec3(ax - 2.6, q.y - (ky - .55), q.z), vec3(2.6, .2, .45));
  float nuk = sdBox(vec3(ax - 2.28, q.y - 6.55, q.z), vec3(2.28, .24, .28));
  float gak = sdBox(vec3(q.x, q.y - 7.35, q.z), vec3(.42, .55, .16));
  return min(min(pil, kas), min(min(shi, nuk), gak));
}
vec3 toriiN(vec3 p){
  vec2 e = vec2(.01, 0.);
  return normalize(vec3(torii(p+e.xyy)-torii(p-e.xyy), torii(p+e.yxy)-torii(p-e.yxy), torii(p+e.yyx)-torii(p-e.yyx)));
}
bool boxHit(vec3 ro, vec3 rd, vec3 bmin, vec3 bmax, out float t0, out float t1){
  vec3 ir = 1./rd;
  vec3 a = (bmin - ro)*ir, b = (bmax - ro)*ir;
  vec3 lo = min(a,b), hi = max(a,b);
  t0 = max(max(lo.x, lo.y), lo.z); t1 = min(min(hi.x, hi.y), hi.z);
  return t1 > max(t0, 0.);
}
float marchTorii(vec3 ro, vec3 rd){
  float t0, t1;
  if(!boxHit(ro, rd, vec3(-6.6, -1., TZ - 1.), vec3(6.6, 9.4, TZ + 1.), t0, t1)) return -1.;
  float t = max(t0, 0.);
  for(int i=0;i<64;i++){
    float d = torii(ro + rd*t);
    if(d < .002*t) return t;
    t += d;
    if(t > t1) break;
  }
  return -1.;
}

vec3 sky(vec3 rd){
  float y = rd.y;
  float sd = max(dot(rd, sunD), 0.);
  vec3 top = vec3(.012,.02,.07), mid = vec3(.2,.08,.18), hor = vec3(.95,.36,.14);
  vec3 c = mix(hor, mid, smoothstep(0., .1, y));
  c = mix(c, top, smoothstep(.06, .45, y));
  c += vec3(1.,.42,.16)*pow(sd, 8.)*.35 + vec3(1.,.7,.4)*pow(sd, 120.)*.55;
  // stars fading out
  vec2 sg = rd.xz/(rd.y + .3)*80.; vec2 sid = floor(sg);
  c += vec3(.9)*pow(h21(sid), 40.)*smoothstep(.15, .0, length(fract(sg) - .5))*smoothstep(.25, .6, y)*(1. - smoothstep(2., 9., L));
  // stratus cloud bands, lit from below by the sun
  if(y > -.02){
    vec2 cp = vec2(rd.x/(y + .045), 1./(y + .045))*vec2(.55, .35) + vec2(L*.02, 0.);
    float cf = fbm2(cp*vec2(1., 2.4), 5);
    float cl = smoothstep(.48, .72, cf)*smoothstep(-.02, .05, y)*(1. - smoothstep(.35, .6, y));
    float lit = smoothstep(.72, .5, cf);
    vec3 cc = mix(vec3(.07,.035,.07), vec3(1.,.45,.2)*.8, pow(sd, 4.)*.8 + lit*.15);
    cc += vec3(1.,.65,.35)*lit*pow(sd, 10.)*1.6;
    c = mix(c, cc, cl*.85);
  }
  // sun disc
  float ang = acos(clamp(dot(rd, sunD), -1., 1.));
  c += vec3(1.,.85,.6)*smoothstep(.02, .017, ang)*13.*smoothstep(-.015, .005, rd.y);
  return c;
}

// the three-legged crow, 八咫烏 — 2D silhouette in its own frame (x forward)
float crowSDF(vec2 p, float flap){
  float body = length(p*vec2(1., 3.2)) - .42;
  body = min(body, length(p - vec2(.44, .07)) - .1);
  // beak
  vec2 b = p - vec2(.52, .06);
  body = min(body, max(abs(b.y) - .035*(1. - b.x/.2), max(-b.x, b.x - .2)));
  // tail fan
  vec2 tq = p - vec2(-.42, 0.);
  body = min(body, max(length(tq) - .26, abs(atan(tq.y, -tq.x)) - .45));
  // wings (both sides of the flap cycle project onto the silhouette)
  for(int s=0;s<2;s++){
    float a = (s == 0 ? 1. : -.35)*flap;
    vec2 w = p - vec2(.05, .02);
    w = rot(a)*w;
    float span = .85;
    float wd = length((w - vec2(-.08, span*.5))*vec2(3.2, 1.)) - span*.5*1.0;
    wd = max(wd, -w.y);
    body = min(body, wd);
  }
  // three legs
  for(int k=0;k<3;k++){
    float x = -.02 + float(k)*.07;
    vec2 lq = p - vec2(x, -.13);
    body = min(body, max(abs(lq.x + lq.y*.25) - .012, max(lq.y, -lq.y - .2)));
  }
  return body;
}

void main(){
  L = uL;
  vec2 uv = getUV();
  float sunY = mix(-.03, .105, smoothstep(0., 15., L));
  sunD = normalize(vec3(0., sunY, 1.));

  vec3 ro = vec3(sin(L*.08)*.6, 1.25 + L*.045, -9. + L*.38);
  vec3 ta = vec3(0., 3.9 + L*.03, TZ);
  mat3 cam = lookAt(ro, ta, 0.);
  float zoom = 1.2;
  vec3 rd = normalize(cam*vec3(uv, zoom));

  vec3 col;
  float tt = marchTorii(ro, rd);
  float tw = rd.y < 0. ? -ro.y/rd.y : 1e9;
  vec3 sunC = vec3(1.,.72,.45);
  if(tt > 0. && tt < tw){
    vec3 p = ro + rd*tt;
    vec3 n = toriiN(p);
    vec3 V = -rd;
    vec3 alb = vec3(.55,.07,.025)*(.8 + .3*n3(p*3.));
    if(p.y > kasagiY(abs(p.x)) + .12) alb = vec3(.03,.025,.025); // black roof cap
    float rim = pow(1. - max(dot(n, V), 0.), 3.);
    col = alb*vec3(.25,.2,.35)*(.3 + .7*max(n.y, 0.))*.45;          // sky fill
    col += alb*vec3(1.,.6,.4)*max(dot(n, vec3(0., .2, -1.)), 0.)*.18;  // warm bounce off the sea
    col += sunC*rim*max(dot(n, sunD) + .4, 0.)*1.3;
    float fog = 1. - exp(-tt*.004);
    col = mix(col, sky(rd)*.8, fog);
  } else if(rd.y < 0.){
    vec3 p = ro + rd*tw;
    // bump-mapped calm sea
    vec2 q = p.xz;
    float e = .06;
    float h0 = fbm3(vec3(q*vec2(.35,.9), L*.4), 4);
    float hx = fbm3(vec3((q + vec2(e,0.))*vec2(.35,.9), L*.4), 4);
    float hz = fbm3(vec3((q + vec2(0.,e))*vec2(.35,.9), L*.4), 4);
    float amp = .9*exp(-tw*.012) + .15;
    vec3 n = normalize(vec3(-(hx - h0)/e*amp, 1., -(hz - h0)/e*amp));
    vec3 rf = reflect(rd, n);
    float fres = .02 + .98*pow(1. - max(dot(n, -rd), 0.), 5.);
    vec3 refl = sky(rf);
    // reflected torii
    float tr = marchTorii(p + n*.01, rf);
    if(tr > 0.){
      vec3 pr = p + rf*tr; vec3 nr = toriiN(pr);
      float rim = pow(1. - max(dot(nr, -rf), 0.), 3.);
      refl = vec3(.05,.015,.015) + sunC*rim*.6;
    }
    vec3 deep = vec3(.006,.01,.025);
    col = mix(deep, refl*.6, sat(fres));
    // sun glitter path
    float gl = pow(max(dot(rf, sunD), 0.), 900.)*60. + pow(max(dot(rf, sunD), 0.), 120.)*1.2;
    col += sunC*gl*smoothstep(-.02, .01, sunY);
    col = mix(col, sky(vec3(rd.x, .0, rd.z))*.8, 1. - exp(-tw*.004));
  } else {
    col = sky(rd);
  }

  // god rays: screen-space march toward the sun, occluded by the torii profile & the horizon
  vec2 ss = project(ro + sunD*1000., ro, cam, zoom);
  {
    float acc = 0., w = 1.;
    float jit = h21(gl_FragCoord.xy + fract(uT)*53.);
    for(int i=0;i<32;i++){
      float fi = (float(i) + jit)/32.;
      vec2 u2 = mix(uv, ss, fi);
      vec3 r2 = normalize(cam*vec3(u2, zoom));
      float lit = step(0., r2.y);
      float tp = (TZ - ro.z)/r2.z;
      vec3 P = ro + r2*tp;
      lit *= step(0., torii2D(P.xy));
      float sd = max(dot(r2, sunD), 0.);
      acc += lit*pow(sd, 40.)*w;
      w *= .97;
    }
    col += sunC*acc/32.*.75*smoothstep(-.02, .02, sunY);
  }

  // 八咫烏 crossing the sun
  float cT = (L - 1.5)/7.;
  if(cT > 0. && cT < 1.){
    vec2 cp = vec2(mix(-1.2, 1.25, cT), ss.y + .05*sin(cT*3.1416) - .005);
    float sz = .11;
    float flap = sin(L*7.)*.95;
    vec2 lp = (uv - cp)/sz;
    lp.y -= sin(L*7. - .6)*.05;
    float d = crowSDF(lp, flap)*sz;
    float m = smoothstep(.0015, -.0005, d);
    col = mix(col, vec3(.004,.003,.003), m);
  }

  // gold dust & petals of light
  col += dustLayer(uv, L, 6., .025, vec3(1.,.75,.4), 2.2)*.35;
  col += dustLayer(uv, L, 14., .04, vec3(1.,.8,.5), 6.6)*.2;
  fragColor = vec4(col, 1.);
}
