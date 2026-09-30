// ============ S4: 八岐大蛇 — the Eight-Headed Serpent ============
// local time 0..15 ; lightning .1/3.2/6.8/9.5/11.8 ; eyes open 7.0 ; slash 13.5 (composite)

float L;
vec3 ro;
vec3 NB[8];      // neck base
float NT[8];     // current top height
float NP[8];     // phase
vec3 HP[8];      // head position
mat3 HF[8];      // head frame (r,u,f)
float gMouth;
int gId; float gPart;
const float HS = 2.0; // head scale // closest neck / part for shading (0 neck, 1 head, 2 horn)

float flashAt(float t0){ float d = L - t0; return d < 0. ? 0. : exp(-d*4.5)*(.65 + .35*sin(d*70.)); }
float flash(){ return flashAt(.1) + flashAt(3.2) + flashAt(6.8) + flashAt(9.5) + flashAt(11.8); }

vec3 neckC(int i, float y){
  vec3 b = NB[i]; float ph = NP[i];
  float k = sat((y - b.y)/max(NT[i] - b.y, 1.));
  float x = b.x + 2.3*sin(y*.21 + ph + L*.75)*k;
  float z = b.z + 1.8*cos(y*.17 + ph*1.3 + L*.55)*k - pow(k, 1.5)*3.5;
  return vec3(x, y, z);
}

float mapS(vec3 p){
  float best = 1e3;
  for(int i=0;i<8;i++){
    vec3 b = NB[i];
    // coarse bound
    float bnd = max(length(vec2(p.x - b.x, p.z - (b.z - 4.))) - 13., p.y - NT[i] - 11.);
    if(bnd > best) continue;
    if(bnd > 1.5){ best = bnd; continue; }
    // neck
    float y = min(p.y, NT[i]);
    vec3 c = neckC(i, y);
    float kk = sat((y - b.y)/max(NT[i] - b.y, 1.));
    float r = 2.0 - .75*kk;
    float dn = (length(p - c) - r)*.55;
    if(dn < best){ best = dn; gId = i; gPart = 0.; }
    // head
    vec3 q = p - HP[i];
    if(dot(q,q) < 190.){
      q = vec3(dot(q, HF[i][0]), dot(q, HF[i][1]), dot(q, HF[i][2]))/HS;
      float sk = sdEllipsoid(q - vec3(0., .2, 0.), vec3(.85, .72, 1.5));
      float sn = sdEllipsoid(q - vec3(0., .08, 1.75), vec3(.52, .4, 1.45));
      float head = smin(sk, sn, .5);
      vec3 qj = q - vec3(0., -.2, -.3);
      qj.yz *= rot(gMouth);
      float jaw = sdEllipsoid(qj - vec3(0., -.22, 1.6), vec3(.55, .26, 1.65));
      head = smin(head, jaw, .25);
      // brow ridges
      vec3 qb = vec3(abs(q.x), q.y, q.z);
      head = smin(head, sdEllipsoid(qb - vec3(.5, .6, .55), vec3(.28, .2, .75)), .2);
      float dh = head*.8*HS;
      if(dh < best){ best = dh; gId = i; gPart = 1.; }
      // horns sweeping back
      float hr = sdCapsule(qb, vec3(.45, .55, -.3), vec3(.95, 1.6, -1.8), .15);
      hr = min(hr, sdCapsule(qb, vec3(.95, 1.6, -1.8), vec3(.9, 2.1, -3.1), .08));
      hr *= HS;
      if(hr < best){ best = hr; gId = i; gPart = 2.; }
    }
  }
  return best;
}

vec3 skyCol(vec3 rd, float F){
  float y = rd.y;
  vec3 c = mix(vec3(.16,.018,.01), vec3(.006,.001,.002), pow(sat(y*1.6 + .1), .6));
  // blood moon
  vec3 md = normalize(vec3(.42, .36, 1.));
  float ma = acos(clamp(dot(rd, md), -1., 1.));
  float disc = smoothstep(.115, .11, ma);
  vec2 mu = (rd.xy - md.xy)*40.;
  float crat = .75 + .35*fbm2(mu*.6 + 3., 4);
  vec3 moon = vec3(1.,.09,.035)*.95*crat*disc + vec3(1.,.08,.03)*exp(-ma*7.)*.35 + vec3(1.,.15,.06)*exp(-ma*25.)*.3;
  // storm clouds racing
  vec2 cp = rd.xz/(rd.y + .15)*1.1 + vec2(L*.06, L*.02);
  float cf = fbm2(cp*1.2, 5);
  float cl = smoothstep(.38, .7, cf);
  vec3 cc = mix(vec3(.02,.003,.004), vec3(.3,.04,.02), smoothstep(.75, .4, cf)*.45) ;
  cc += vec3(.9,.85,1.)*F*.35*(1. - cl*.5);
  c += moon*(1. - cl*.85);
  c = mix(c, cc, cl*smoothstep(-.05, .2, y));
  c += vec3(.8,.8,1.)*F*.08;
  return c;
}

float ridgeNear(float az){ return -.045 + .13*fbm2(vec2(az*2.6, 3.), 4) - .04 + .05*n2(vec2(az*9., 1.)); }
float ridgeFar(float az){ return .0 + .12*fbm2(vec2(az*1.4, 9.), 4); }

float bolt(vec2 uv, float t0, float seed){
  float d = L - t0; if(d < 0. || d > .9) return 0.;
  float x0 = (h11(seed) - .5)*1.6;
  float grow = sat(d/.07);
  float yTop = .45, yBot = mix(.45, -.08, grow);
  if(uv.y < yBot || uv.y > yTop) return 0.;
  float yy = uv.y;
  float x = x0 + (fbm2(vec2(yy*3., seed), 4) - .5)*.5 + (n2(vec2(yy*22., seed*3.)) - .5)*.05;
  float dd = abs(uv.x - x);
  float b = exp(-dd*650.)*3. + exp(-dd*60.)*.35;
  // branch
  float xb = x + (yTop - yy)*.0 + (yy - .2)*.35*(h11(seed+1.) - .5)*2. + (n2(vec2(yy*30., seed*5.)) - .5)*.04;
  b += (exp(-abs(uv.x - xb)*700.)*1.5)*step(yy, .25)*step(.02, yy);
  float env = exp(-d*6.)*(.6 + .4*sin(d*90.));
  return b*env;
}

float rain(vec2 uv){
  float acc = 0.;
  for(int k=0;k<3;k++){
    float fk = float(k);
    vec2 q = rot(.2)*uv;
    q.x *= 110. + fk*70.;
    q.y = q.y*(2. + fk*.8) + L*(7. + fk*2.5);
    float colm = floor(q.x);
    float rnd = h11(colm*.37 + fk*11.);
    float yy = fract(q.y + rnd*13.);
    float s = smoothstep(0., .1, yy)*smoothstep(.2, .1, yy);
    float w = pow(1. - abs(fract(q.x) - .5)*2., 6.);
    acc += s*w*step(.55, rnd)*(.35 - fk*.08);
  }
  return acc;
}

void main(){
  L = uL;
  vec2 uv = getUV();
  float F = flash();

  // --- set up the eight
  float order[8] = float[8](3., 5., 1., 6., 0., 7., 2., 4.);
  for(int i=0;i<8;i++){
    float fi = float(i);
    float hsh = h11(fi*7.31 + 2.);
    NB[i] = vec3(-13.5 + fi*3.85 + (hsh - .5)*1.5, -10., 23. + h11(fi*3.7)*8.);
    NP[i] = fi*1.7 + hsh*3.;
    float st = .5 + order[i]*.62;
    float k = sat((L - st)/3.6); k = k*k*(3. - 2.*k);
    NT[i] = mix(-12., 15. + hsh*9., k) + .6*sin(L*1.3 + fi);
  }
  gMouth = .15 + .3*smoothstep(7., 7.6, L)*(.7 + .3*sin(L*3.));

  ro = vec3(sin(L*.15)*1.2, .6 + L*.04, -15. + L*.3) + shakeOffset(uShake*1.3, uT);
  vec3 ta = vec3(0., 13.5, 22.);
  mat3 cam = lookAt(ro, ta, sin(L*.2)*.03);
  float zoom = 1.12;
  vec3 rd = normalize(cam*vec3(uv, zoom));

  for(int i=0;i<8;i++){
    vec3 top = neckC(i, NT[i]);
    vec3 tan = normalize(top - neckC(i, NT[i] - 1.5));
    vec3 toCam = normalize(ro + vec3(0., -2., 0.) - top);
    vec3 f = normalize(mix(tan, toCam, .5) + vec3((NB[i].x > 0. ? .55 : -.55) + sin(NP[i] + L*.6)*.3, -.25, 0.));
    vec3 r = normalize(cross(vec3(0,1,0), f));
    vec3 u = cross(f, r);
    HF[i] = mat3(r, u, f);
    HP[i] = top + f*1.4 + u*.5;
  }

  // --- march
  float t = 1., d; bool hit = false;
  for(int i=0;i<130;i++){
    d = mapS(ro + rd*t);
    if(d < .003*t){ hit = true; break; }
    t += d*.85;
    if(t > 110.) break;
  }
  float az = atan(rd.x, rd.z);
  vec3 col = skyCol(rd, F);
  // far ridge (behind the serpents)
  float rf = ridgeFar(az);
  if(rd.y < rf) col = mix(vec3(.04,.006,.005), vec3(.09,.014,.01), smoothstep(rf - .1, rf, rd.y)) + vec3(.5,.5,.6)*F*.04;

  if(hit){
    vec3 p = ro + rd*t;
    int id = gId; float part = gPart;
    vec2 e = vec2(.02, 0.);
    vec3 n = normalize(vec3(mapS(p+e.xyy)-mapS(p-e.xyy), mapS(p+e.yxy)-mapS(p-e.yxy), mapS(p+e.yyx)-mapS(p-e.yyx)));
    gId = id; gPart = part;
    // scales
    vec3 c = neckC(id, min(p.y, NT[id]));
    float around = atan(p.x - c.x, p.z - c.z);
    vec2 g = vec2(around*5.5, p.y*3.);
    g.x += floor(g.y)*.5;
    vec2 fg = fract(g) - .5;
    float sc = length(fg*vec2(1., 1.25));
    float scaleEdge = smoothstep(.35, .5, sc);
    if(part > .5){ scaleEdge = smoothstep(.55, .75, n3(p*5.)); }
    n = normalize(n + vec3(fg.x, 0., fg.y)*.35*(1. - part*.6) + (vec3(n3(p*6.), n3(p*6.+5.), n3(p*6.+9.)) - .5)*.3);
    vec3 alb = mix(vec3(.05,.07,.055), vec3(.02,.025,.022), scaleEdge);
    alb = mix(alb, vec3(.09,.06,.04), part == 2. ? 1. : 0.);
    vec3 V = -rd;
    // key: blood moon behind, rim
    vec3 md = normalize(vec3(.42, .36, 1.));
    float rim = pow(1. - max(dot(n, V), 0.), 3.);
    vec3 lit = alb*vec3(.18,.03,.02)*(.25 + .75*max(n.y, 0.));
    lit += vec3(1.,.1,.03)*pow(rim, 1.6)*(.25 + 1.2*max(dot(n, md), 0.))*.9;
    // lightning key
    vec3 lf = normalize(vec3(-.3, .8, -.45));
    lit += (alb*2. + .01)*vec3(.75,.8,1.)*max(dot(n, lf), 0.)*F*3.;
    vec3 hv = normalize(lf + V);
    lit += vec3(.8,.85,1.)*pow(max(dot(n, hv), 0.), 40.)*F*2.*(1. - scaleEdge*.6);
    vec3 hm = normalize(md + V);
    lit += vec3(1.,.3,.15)*pow(max(dot(n, hm), 0.), 30.)*.4;
    if(part == 1.){
      vec3 q = p - HP[id];
      q = vec3(dot(q, HF[id][0]), dot(q, HF[id][1]), dot(q, HF[id][2]))/HS;
      float mz = (q.y + .12)/.09;
      float mouthZone = smoothstep(.6, 1.6, q.z)*exp(-mz*mz)*smoothstep(.7, .2, abs(q.x));
      lit += vec3(1.,.18,.03)*mouthZone*(.2 + 1.6*smoothstep(6.9, 7.4, L))*(.7 + .3*n3(q*3. + vec3(0., L*4., 0.)));
    }
    col = lit;
    col = mix(col, vec3(.1,.013,.008) + vec3(.4)*F*.08, 1. - exp(-t*.01));
  }

  // eyes — the moment they open
  float eyeK = smoothstep(6.9, 7.2, L);
  for(int i=0;i<8;i++){
    if(NT[i] < -5.) continue;
    for(int s=-1;s<=1;s+=2){
      vec3 ep = HP[i] + (HF[i][0]*(.6*float(s)) + HF[i][1]*.5 + HF[i][2]*.8)*HS;
      vec3 v = ep - ro; float te = dot(v, rd);
      if(hit && te > t + .6) continue;
      float de = length(v - rd*te);
      float blink = .6 + .4*sin(L*2. + float(i));
      vec3 ec = vec3(1.,.12,.03);
      col += ec*(smoothstep(.22, .08, de)*(.3 + 16.*eyeK) + exp(-de*2.2)*.3*eyeK*blink);
      col += ec*exp(-abs(dot(v - rd*te, cam[1]))*30.)*exp(-de*1.2)*.4*eyeK; // anamorphic
    }
  }

  // near ridge in front of everything
  float rn = ridgeNear(az);
  float below = smoothstep(rn + .002, rn - .002, rd.y);
  vec3 ridgeC = vec3(.004,.001,.001) + vec3(1.,.12,.05)*exp(-max(rn - rd.y, 0.)*200.)*.08 + vec3(.6,.6,.8)*F*.015;
  col = mix(col, ridgeC, below);

  // lightning bolts
  col += vec3(.85,.88,1.)*(bolt(uv, .1, 3.) + bolt(uv, 3.2, 17.) + bolt(uv, 6.8, 29.) + bolt(uv, 9.5, 41.) + bolt(uv, 11.8, 53.));
  // rain
  col += vec3(.6,.55,.6)*rain(uv)*(.35 + F*1.5);
  // embers / ash
  col += dustLayer(uv, L, 10., -.06, vec3(1.,.3,.1), 4.4)*.25;

  // the blade catches the light: a glint before the cut
  float gl = exp(-pow((L - 13.25)*5., 2.));
  vec2 gp = vec2(-.62, -.24);
  vec2 dg = uv - gp;
  col += vec3(.85,.9,1.)*gl*(.002/(dot(dg,dg) + .0002) + (exp(-abs(dg.y)*300.)*exp(-abs(dg.x)*6.) + exp(-abs(dg.x)*300.)*exp(-abs(dg.y)*10.))*2.);

  fragColor = vec4(col, 1.);
}
