// ============ S2: 国生み — the Heavenly Jeweled Spear stirs the primordial sea ============
// local time 0..17 ; spear in 0.6 ; stir 4.0 ; lift 9.0 ; drop falls ; impact 12.8

float L;
const vec2 C = vec2(0., 16.);
float swirl, swirlPh, isl, imp;
vec3 spTip; // spear tip
vec3 spDir; // spear axis (tip -> heaven)
float dropY;

vec3 sky(vec3 rd){
  float y = max(rd.y, 0.);
  vec3 zen = vec3(.004,.01,.03), hor = vec3(.10,.06,.08);
  vec3 c = mix(hor, zen, pow(y, .45));
  vec3 sunD = normalize(vec3(.35,.03,1.));
  float sd = max(dot(rd, sunD), 0.);
  c += vec3(1.,.45,.2)*pow(sd, 12.)*.3 + vec3(1.,.7,.4)*pow(sd, 120.)*.6;
  // cloud deck
  if(rd.y > 0.){
    vec2 cp = rd.xz/(rd.y+.06)*.9 + vec2(L*.012, 0.);
    float cf = fbm2(cp*1.1, 5);
    float cl = smoothstep(.46, .72, cf);
    float edge = smoothstep(.72, .5, cf)*cl;
    vec3 cc = mix(vec3(.006,.008,.018), vec3(.3,.13,.1)*.5, pow(sd,3.)) + vec3(1.,.5,.25)*edge*pow(sd,4.)*.5;
    c = mix(c, cc, cl*smoothstep(0.,.2,rd.y)*.9);
  }
  // 天浮橋 — the Floating Bridge of Heaven: a luminous spectral arc
  vec3 A = normalize(vec3(-.1,-.32,1.));
  float ang = acos(clamp(dot(rd, A), -1., 1.));
  float x = (ang - .78)/.045;
  if(abs(x) < 2.){
    vec3 spec = sat(vec3(1.2-abs(x-.8)*1.4, 1.1-abs(x)*1.4, 1.2-abs(x+.8)*1.4));
    float fade = smoothstep(0.,.12,rd.y) * (.55 + .45*n2(rd.xz*30.));
    c += (spec*.13 + vec3(1.,.88,.7)*exp(-x*x*3.)*.3) * fade * smoothstep(0., 3., L);
  }
  // high stars behind thin cloud
  vec2 sg = rd.xz/(rd.y+.2)*70.;
  vec2 sid = floor(sg), sf = fract(sg)-.5;
  vec2 so = (h22(sid)-.5)*.7;
  float sb = pow(h21(sid+3.1), 18.);
  c += vec3(.85,.9,1.)*sb*smoothstep(.12, .0, length(sf-so))*smoothstep(.1,.5,rd.y)*1.5;
  return c;
}

float waterH(vec2 p){
  vec2 d = p - C;
  float r = length(d);
  d = rot(swirlPh/(.7 + r*.28)) * d;
  vec2 q = C + d;
  float h = n3(vec3(q*.22, L*.3)) + n3(vec3(q*.5 + 7., L*.45))*.45 + n3(vec3(q*1.15 + 3., L*.7))*.18;
  h = (h - .815)*1.5;
  float a = atan(d.y, d.x);
  h += swirl*.3*sin(a*3. + r*.8 - L*3.)*exp(-r*.09);
  h -= swirl*2.8*exp(-r*r*.045);
  if(imp > 0.) h += 1.1*exp(-pow(r - imp*7.5, 2.)*.35)*exp(-imp*.45);
  return h;
}
float landH(vec2 p){
  if(isl <= 0.) return -50.;
  vec2 d = p - C;
  float r2 = dot(d,d);
  if(r2 > 900.) return -50.;
  float m = exp(-r2*.022);
  float n = fbm2(p*.16, 4);
  float rid = 1. - abs(2.*n2(p*.4+5.) - 1.);
  float shape = m*(.5 + 1.2*n) + m*m*rid*.35;
  return shape*4.6 - 11. + isl*10.2;
}
float mapH(vec2 p, out float mat){
  float w = waterH(p), l = landH(p);
  mat = l > w ? 1. : 0.;
  return max(w, l);
}

vec3 spearGlow(vec3 ro, vec3 rd, float tMax){
  vec3 acc = vec3(0.);
  float tr, hs;
  vec3 top = spTip + spDir*70.;
  float d = raySeg(ro, rd, spTip, top, tr, hs);
  float s = hs*70.;
  float w = .09 + .32*sat(s/1.1)*(1. - smoothstep(1.9, 3.4, s));
  float vis = tr < tMax ? 1. : .12;
  float core = smoothstep(w, w*.25, d);
  vec3 cc = mix(vec3(1.,.93,.75), vec3(1.,.72,.35), sat(s/20.));
  acc += cc*core*3.5*vis;
  acc += cc*exp(-d*5.)*.35*vis*exp(-s*.02);
  acc += vec3(1.,.6,.3)*exp(-d*1.2)*.04*vis;
  // jewels on the shaft: jade, coral, pearl
  vec3 jc[3]; jc[0] = vec3(.2,1.,.55); jc[1] = vec3(1.,.25,.2); jc[2] = vec3(.9,.9,1.);
  for(int i=0;i<3;i++){
    vec3 jp = spTip + spDir*(3.2 + float(i)*.75);
    vec3 v = jp - ro; float tj = dot(v, rd);
    float dj = length(v - rd*tj);
    float tw = .7 + .3*sin(uT*9. + float(i)*2.);
    acc += jc[i]*(smoothstep(.13, .05, dj)*3. + exp(-dj*8.)*.5*tw) * (tj < tMax ? 1. : .1);
  }
  return acc;
}

void main(){
  L = uL;
  vec2 uv = getUV();

  // --- choreography
  float down = smoothstep(.6, 4.6, L);
  float up   = smoothstep(9.0, 10.9, L);
  float stir = smoothstep(4.0, 5.6, L)*(1. - smoothstep(8.4, 9.4, L));
  float sa = (L - 4.)*2.1;
  vec2 sxz = C + vec2(cos(sa), sin(sa))*1.1*stir;
  float tipY = mix(46., -2.8, down*down*(3.-2.*down)) + up*9.5;
  spTip = vec3(sxz.x, tipY, sxz.y);
  spDir = normalize(vec3(-.12, 1., -.18));
  swirl = smoothstep(4.2, 8.5, L)*(1. - .55*smoothstep(11., 16., L));
  swirlPh = swirl*(L - 4.)*1.9;
  isl = smoothstep(12.8, 16.2, L); isl = isl*isl*(3.-2.*isl);
  imp = max(L - 12.8, 0.) * step(12.8, L);
  float fall = sat((L - 10.9)/1.9);
  dropY = mix(tipY, 0., fall*fall);

  // --- camera
  vec3 ro = vec3(-4. + L*.22, 5.2 + L*.12, -5.5 + L*.35) + vec3(-1.5, 3.2, -9.)*smoothstep(12.8, 17., L) + shakeOffset(uShake, uT);
  float look = smoothstep(.2, 5.2, L);
  vec3 ta = vec3(C.x + .5, mix(14., .8, look) + 1.2*isl, C.y);
  mat3 cam = lookAt(ro, ta, .02);
  float zoom = 1.3;
  vec3 rd = normalize(cam*vec3(uv, zoom));

  // --- heightfield march
  float t = .5, mat = 0., hit = 0.;
  float tMax = 160.;
  vec3 p;
  for(int i=0;i<120;i++){
    p = ro + rd*t;
    float h = mapH(p.xz, mat);
    float dy = p.y - h;
    if(dy < .003*t){ hit = 1.; break; }
    t += max(dy*.42, .015*t);
    if(t > tMax) break;
  }
  vec3 col;
  vec3 skyc = sky(rd);
  if(hit > .5){
    // refine
    vec2 e = vec2(.04 + t*.002, 0.);
    float m2;
    float hc = mapH(p.xz, m2);
    vec3 n = normalize(vec3(mapH(p.xz - e.xy, m2) - mapH(p.xz + e.xy, m2), 2.*e.x, mapH(p.xz - e.yx, m2) - mapH(p.xz + e.yx, m2)));
    vec3 Lp = vec3(spTip.x, max(spTip.y, 0.)+.8, spTip.z);
    float sI = 9.*exp(-max(spTip.y, 0.)*.18)*step(.3, down);
    vec3 toL = Lp - p; float dl = length(toL); toL /= dl;
    vec3 sunD = normalize(vec3(.35,.03,1.));
    vec2 d = p.xz - C; float r = length(d);
    if(mat < .5){
      // ---- water
      float fres = .02 + .98*pow(1. - max(dot(n, -rd), 0.), 5.);
      vec3 rf = reflect(rd, n);
      vec3 refl = sky(rf);
      vec3 base = vec3(.002,.01,.016);
      // bioluminescent spiral arms
      vec2 dd = rot(swirlPh/(.7 + r*.28))*d;
      float a = atan(dd.y, dd.x);
      float arms = pow(sat(.5+.5*sin(a*3. + r*.8 - L*3.)), 6.);
      float bio = swirl*arms*exp(-r*.085)*(.5+.8*n3(vec3(p.xz*.8, L)));
      vec3 bioC = mix(vec3(.1,.8,.9), vec3(1.,.7,.3), sat(1.-r*.06));
      base += bioC*bio*1.3;
      // light pool where the spear pierces the sea
      base += vec3(1.,.75,.4)*sI/(1. + dl*dl*.6)*.8;
      // shockwave ring & first land's glow
      if(imp > 0.) base += vec3(1.,.7,.35)*exp(-pow(r - imp*7.5, 2.)*.5)*exp(-imp*.6)*3.;
      base += vec3(1.,.45,.15)*isl*exp(-r*.25)*.5*(1. - smoothstep(14., 17., L)*.5);
      float spec = pow(max(dot(reflect(-toL, n), -rd), 0.), 60.)*sI*.5;
      float sunSpec = pow(max(dot(rf, sunD), 0.), 200.)*2.;
      col = mix(base, refl, fres) + vec3(1.,.8,.5)*(spec + sunSpec);
      // crest foam
      col += vec3(.6,.7,.75)*smoothstep(.35, .8, hc - (-swirl*2.8*exp(-r*r*.045)))*.08;
    } else {
      // ---- newborn land: black basalt with molten veins
      float rid = 1. - abs(2.*fbm2(p.xz*.5 + 3., 3) - 1.);
      float veins = pow(rid, 22.);
      float cool = smoothstep(13.5, 17., L);
      vec3 alb = vec3(.035,.03,.028);
      float dif = max(dot(n, sunD*vec3(1.,6.,1.)/length(sunD*vec3(1.,6.,1.))), 0.);
      col = alb*(dif*vec3(1.,.6,.4)*.8 + .12*vec3(.3,.35,.5));
      col += alb*sI*max(dot(n, toL), 0.)/(1. + dl*dl*.3);
      col += vec3(1.,.32,.06)*veins*(2.4 - 1.5*cool)*(.6 + .4*n3(vec3(p.xz, L*.8)));
      col += vec3(1.,.45,.15)*pow(sat(p.y + .6), .5)*0. ;
      // wet rim near waterline
      col += vec3(1.,.6,.3)*exp(-abs(p.y - waterH(p.xz))*6.)*.25*isl;
      // rim light
      col += vec3(1.,.55,.3)*pow(1. - max(dot(n, -rd), 0.), 4.)*.25;
    }
    // atmosphere
    float fog = 1. - exp(-t*.013);
    col = mix(col, skyc*.8 + vec3(.012,.01,.014), fog);
  } else {
    col = skyc;
  }

  // the spear itself + drops
  col += spearGlow(ro, rd, hit > .5 ? t : 1e4) * step(.4, L);
  if(L > 10.9 && L < 12.85){
    vec3 dp = vec3(spTip.x, dropY, spTip.z);
    vec3 v = dp - ro; float td = dot(v, rd); float dd = length(v - rd*td);
    col += vec3(1.,.85,.6)*(smoothstep(.12,.04,dd)*4. + exp(-dd*6.)*.8);
    // trail
    float tr, hs; float dtl = raySeg(ro, rd, dp, dp + vec3(0., 2.5, 0.), tr, hs);
    col += vec3(1.,.7,.4)*exp(-dtl*25.)*(1.-hs)*.8;
  }
  // pillar of light at the moment of birth
  if(imp > 0.){
    float tr, hs;
    float dpl = raySeg(ro, rd, vec3(C.x, -1., C.y), vec3(C.x, 60., C.y), tr, hs);
    float pw = .3 + imp*.5;
    col += vec3(1.,.8,.55)*exp(-dpl/pw)*exp(-imp*1.1)*4.*(1. - hs*.7);
    col += vec3(1.,.9,.7)*exp(-imp*6.)*.6; // flash
  }
  // drifting sparks over the sea
  col += dustLayer(uv, L, 9., .02, vec3(1.,.75,.45), 3.3)*.25*(.3 + swirl);
  fragColor = vec4(col, 1.);
}
