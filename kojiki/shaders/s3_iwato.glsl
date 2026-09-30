// ============ S3: 天岩戸 — the Heavenly Rock Cave ============
// local time 0..18 ; drum dance 5..12.4 ; door rolls 12.6 ; burst 13.5

float L;
float openK, burst, crackI;
float bx; // boulder x
const float BX0 = 1.05;
const vec3 CAVE = vec3(0., 2.2, 0.4);

float sdCave(vec3 p){
  // arch-shaped tunnel into the cliff
  vec3 q = p - vec3(0., 0., 0.);
  float arch = length(vec2(q.x*.95, max(q.y - 3.2, 0.))) - 2.5;
  float box = max(arch, -q.y - .2);
  return max(box, -(q.z + .6));   // opening starts a bit in front of the face
}
float cliff(vec3 p){
  float m = smoothstep(3.5, 9., length(p.xy - vec2(0., 3.)));
  float disp = (fbm3(p*vec3(.3,.09,.3), 4) - .5)*(1.5 + 3.5*m) + (fbm3(p*vec3(.9,.3,.9)+4., 2) - .5)*.8 + (n3(p*1.6) - .5)*.25;
  float d = -p.z*.8 + disp - m*1.2*sin(p.x*.2);
  float top = 13.5 + (fbm3(vec3(p.x*.12, 0., p.z*.2), 3) - .5)*12. + p.z*.3;
  d = max(d, (p.y - top)*.7);
  d = max(d, -sdCave(p));
  return d;
}
float boulder(vec3 p){
  vec3 q = p - vec3(bx, 3.1, -1.3);
  q.xy *= rot(-(bx - BX0)*.22);            // it rolls as it moves
  float d = sdRoundBox(q, vec3(2.1, 2.6, .7), 1.1);
  d += (fbm3(q*.7 + 11., 3) - .5)*.8 + (n3(q*3.) - .5)*.08;
  return d;
}
float ground(vec3 p){ return p.y + (fbm3(vec3(p.xz*.4, 1.), 3) - .5)*.5 + .15; }
float map(vec3 p, out float m){
  float c = cliff(p), b = boulder(p), g = ground(p);
  float d = c; m = 0.;
  if(b < d){ d = b; m = 1.; }
  if(g < d){ d = g; m = 2.; }
  return d;
}
float mapD(vec3 p){ float m; return map(p, m); }
vec3 normal(vec3 p){
  vec2 e = vec2(.012, 0.);
  return normalize(vec3(mapD(p+e.xyy)-mapD(p-e.xyy), mapD(p+e.yxy)-mapD(p-e.yxy), mapD(p+e.yyx)-mapD(p-e.yyx)));
}

// bonfire billboard
vec3 fire(vec3 ro, vec3 rd, vec3 fp, float tMax, float seed){
  // intersect a camera-facing vertical plane through fp
  vec3 nrm = normalize(vec3(ro.x - fp.x, 0., ro.z - fp.z));
  float den = dot(rd, nrm); if(abs(den) < 1e-4) return vec3(0);
  float t = dot(fp - ro, nrm)/den;
  if(t < 0. || t > tMax) return vec3(0.);
  vec3 p = ro + rd*t - fp;
  vec3 side = normalize(cross(vec3(0,1,0), nrm));
  vec2 q = vec2(dot(p, side), p.y);
  vec3 c = vec3(0.);
  // flame
  float y = q.y;
  if(y > -.1 && y < 2.6){
    float nse = fbm3(vec3(q.x*2.2, y*1.6 - uT*3.2, seed), 3);
    float w = .55*(1. - smoothstep(0., 2.3, y))*(.6 + .8*nse) + .05;
    float f = smoothstep(w, w*.2, abs(q.x + (nse - .5)*.5*y));
    f *= smoothstep(-.1, .15, y)*(1. - smoothstep(1.2, 2.5, y + nse*.8));
    vec3 fc = mix(vec3(1.,.8,.45), vec3(1.,.3,.04), sat(y*.7 + (1.-f)*.6));
    c += fc*f*1.3;
  }
  c += vec3(1.,.4,.1)*exp(-length(q - vec2(0., .6))*2.2)*.08;   // halo
  // brazier stand
  return c;
}

void main(){
  L = uL;
  vec2 uv = getUV();

  openK = smoothstep(12.6, 14.6, L); openK = openK*openK*(3.-2.*openK);
  burst = smoothstep(13.3, 13.9, L);
  bx = mix(BX0, 7.8, openK);
  float pulse = uBeat;
  crackI = (.25 + 1.8*pulse + smoothstep(5., 12.5, L)*1.2)*(1. - burst) + burst*0.;

  // camera: slow push, shake from door
  vec3 ro = vec3(sin(L*.1)*1.2, .8 + L*.02, -21. + L*.28) + shakeOffset(uShake, uT);
  vec3 ta = vec3(0., 6.2, 0.);
  mat3 cam = lookAt(ro, ta, 0.);
  float zoom = 1.05;
  vec3 rd = normalize(cam*vec3(uv, zoom));

  // light sources
  vec3 F1 = vec3(-6.5, 1.1, -7.5), F2 = vec3(6.8, 1.1, -7.8);
  float fl1 = .8 + .2*n3(vec3(uT*6., 0, 0)) + .15*sin(uT*23.);
  float fl2 = .8 + .2*n3(vec3(uT*6., 9., 0)) + .15*sin(uT*19.+1.);
  vec3 crackP = vec3(-2.45, 3.2, -.4);
  vec3 caveL  = vec3(0., 3.2, -.2 - openK*2.5);

  float t = .1, m = 0.; bool hit = false;
  for(int i=0;i<110;i++){
    vec3 p = ro + rd*t;
    float d = map(p, m);
    if(d < .002*t){ hit = true; break; }
    t += d*.75;
    if(t > 40.) break;
  }
  vec3 col = vec3(0.);
  vec3 sun = vec3(1.,.82,.55);
  float inCave = 0.;
  if(hit){
    vec3 p = ro + rd*t;
    vec3 n = normal(p);
    // surface detail
    n = normalize(n + (vec3(n3(p*4.), n3(p*4.+7.), n3(p*4.+13.)) - .5)*.35);
    float cv = sdCave(p);
    inCave = (m < .5 && cv > -.05 && p.z > -.5) ? smoothstep(-.6, 1.6, p.z) : 0.;
    vec3 alb = m == 1. ? vec3(.10,.09,.085) : m == 2. ? vec3(.06,.055,.05) : vec3(.085,.08,.075);
    alb *= .7 + .6*n3(p*2.);
    // ambient: faint cold night
    vec3 lit = alb*vec3(.02,.03,.06)*(.4 + .6*max(n.y,0.)) + alb*vec3(.01,.015,.03);
    lit += alb*vec3(.25,.35,.6)*.55*pow(max(dot(n, normalize(vec3(-.6,.7,-.45))), 0.), 1.5)*(1. - openK*.5);
    // bonfires
    for(int k=0;k<2;k++){
      vec3 fp = k == 0 ? F1 : F2; float fl = k == 0 ? fl1 : fl2;
      vec3 l = fp + vec3(0,.6,0) - p; float dl = length(l); l /= dl;
      lit += alb*vec3(1.,.42,.12)*max(dot(n, l), 0.)*fl*6./(1. + dl*dl*.8);
    }
    // the crack of light
    { vec3 l = crackP - p; float dl = length(l); l /= dl;
      lit += alb*sun*max(dot(n, l), 0.)*crackI*2.5/(1. + dl*dl*2.); }
    // the returned sun
    { vec3 l = caveL - p; float dl = length(l); l /= dl;
      float I = openK*9. + burst*6.*exp(-max(L-13.9,0.)*.8);
      lit += alb*sun*max(dot(n, l)*.8 + .2, 0.)*I/(1. + dl*dl*.5); }
    col = lit;
    // interior of the cave glows: goddess light
    float inner = smoothstep(-.8, 1.4, p.z)*step(cv, .08)*step(m, .5);
    col += sun*inner*(crackI*6. + openK*5. + burst*6.)*(0.5 + p.z*.3);
    // fog
    col = mix(col, vec3(.006,.008,.015) + sun*openK*.05, 1. - exp(-t*.025));
  } else {
    // starless void sky with faint cloud
    col = vec3(.003,.004,.009) + vec3(.012,.01,.018)*fbm2(uv*3. + L*.02, 3);
    vec2 sg = uv*90.; vec2 sid = floor(sg);
    col += vec3(.7,.75,1.)*pow(h21(sid), 30.)*smoothstep(.15,.0,length(fract(sg)-.5))*(1.-openK)*.6;
    col += sun*openK*.12*smoothstep(.6,-.2,uv.y);
  }

  // bonfires & ember sparks
  col += fire(ro, rd, F1, hit ? t : 1e4, 1.)*fl1;
  col += fire(ro, rd, F2, hit ? t : 1e4, 7.)*fl2;
  // brazier posts
  // volumetric shafts: march in screen space toward the cave, testing an analytic mask of the opening
  vec2 sc = project(vec3(0., 3.2, 0.), ro, cam, zoom);
  vec2 dv = uv - sc; float r = length(dv);
  float shaft = 0.;
  {
    float w = 1., jit = h21(gl_FragCoord.xy + fract(uT)*37.);
    for(int i=0;i<40;i++){
      float fi = (float(i) + jit)/40.;
      vec2 u2 = mix(uv, sc, fi*.97);
      vec3 r2 = normalize(cam*vec3(u2, zoom));
      float tp = (-.62 - ro.z)/r2.z;
      vec3 P = ro + r2*tp;
      float arch = step(length(vec2(P.x*.95, max(P.y - 3.2, 0.))), 2.45)*step(-.1, P.y);
      vec2 bq = (P.xy - vec2(bx, 3.1))*rot(-(bx - BX0)*.22);
      float cover = step(abs(bq.x), 3.35)*step(abs(bq.y), 3.7);
      float m = arch*(1. - cover);
      m *= .5 + .9*n2(vec2(atan(P.y-3.2, P.x)*7., L*.3));
      shaft += m*w; w *= .965;
    }
    shaft /= 17.;
  }
  float shaftI = crackI*.9*(1. - openK) + openK*1.1 + burst*1.4*exp(-max(L-13.5,0.)*.5);
  col += sun*shaft*shaftI*(.6 + .4*exp(-r*1.5));
  col += sun*(openK*.12 + burst*.5*exp(-max(L-13.5,0.)*.7))*exp(-r*2.5);
  vec2 cp = project(crackP, ro, cam, zoom);
  col += sun*crackI*exp(-abs(uv.x - cp.x)*120.)*exp(-abs(uv.y - cp.y)*14.)*.25;

  // 八咫鏡 — the sacred mirror: octagonal halo rings at the moment of return
  float mir = burst*(1. - smoothstep(15.5, 18., L));
  if(mir > 0.){
    vec2 q = dv*rot(L*.05);
    q = abs(q);
    float oct = max(max(q.x, q.y), (q.x + q.y)*.7071);
    float R = .11 + (L - 13.5)*.025;
    float rings = exp(-abs(oct - R)*260.)*1.2 + exp(-abs(oct - R*1.5)*200.)*.6 + exp(-abs(oct - R*2.2)*140.)*.35;
    rings += exp(-abs(length(dv) - R*2.9)*120.)*.2;
    col += vec3(1.,.85,.6)*rings*mir;
  }
  // embers rising from the fires, dust in the sun afterwards
  vec3 emb = dustLayer(uv + vec2(0., -uL*.0), L, 7., .12, vec3(1.,.45,.12), 1.7) + dustLayer(uv, L, 13., .2, vec3(1.,.55,.2), 5.2);
  col += emb*(.35 + .6*pulse)*(1. - burst*.6);
  col += dustLayer(uv, L, 5., .03, sun, 9.1)*(openK*.9);
  fragColor = vec4(col, 1.);
}
