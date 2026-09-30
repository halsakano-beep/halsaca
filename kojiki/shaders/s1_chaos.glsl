// ============ S1: 天地開闢 — primordial chaos parts into heaven and earth ============
// local time 0..15 ; spark 0.8 ; divide 9.5 ; three gods 12.0/12.6/13.2

float L;
float divideK;   // 0..1 heaven/earth separation
float birthR;    // radius of the expanding cloud

float density(vec3 p, out float ridge, out float side){
  side = p.y;
  vec3 q = p;
  // heaven rises, earth sinks
  float dt = max(L-9.5, 0.);
  q.y -= sign(p.y) * divideK * (0.4 + dt*0.55);
  q.xy *= rot(q.z*.11 + L*.045);
  vec2 w = vec2(fbm3(q*.32 + vec3(0.,0.,L*.05), 3), fbm3(q*.32 + vec3(5.2,1.3,-L*.04), 3));
  float f = fbm3(q*.5 + vec3(w*2.6, L*.07), 4);
  f = cn(f);
  ridge = 1. - abs(2.*f - 1.);
  float d = smoothstep(.47, .85, f);
  // the gap between heaven and earth
  float gap = divideK * (0.25 + dt*0.35);
  d *= mix(1., smoothstep(gap*.6, gap*1.6 + .01, abs(p.y)), divideK);
  // the cloud is born from a single point
  float r = length(p - vec3(0,0,9.));
  d *= smoothstep(birthR, birthR - 3., r);
  return d;
}

void main(){
  L = uL;
  vec2 uv = getUV();
  divideK = smoothstep(9.3, 11.8, L);
  birthR = mix(0., 40., smoothstep(0.9, 7.5, L));

  float z = L*0.9;
  vec3 ro = vec3(0., 0.05, z) + shakeOffset(uShake, uT);
  vec3 ta = ro + vec3(sin(L*.13)*.15, .02 - divideK*0.03, 1.);
  mat3 cam = lookAt(ro, ta, sin(L*.2)*.06*(1.-divideK));
  float zoom = 1.25;
  vec3 rd = normalize(cam * vec3(uv, zoom));

  vec3 col = vec3(0.);
  float T = 1.;
  float t = .3 + h21(gl_FragCoord.xy + fract(uT)*91.)*.25;
  vec3 gold = vec3(1.0, .62, .22);
  for(int i=0;i<64;i++){
    vec3 p = ro + rd*t;
    float ridge, side;
    float d = density(p, ridge, side);
    float dt = .13 + t*.03;
    if(d > .002){
      float up = smoothstep(-.2, .2, side);
      // chaos palette: ink indigo, violet, and gold filaments
      vec3 base = mix(vec3(.006,.01,.035), vec3(.05,.012,.06), cn(n3(p*.7+3.)));
      vec3 fil  = gold * pow(ridge, 16.) * 2.4 + vec3(.5,.25,1.)*pow(ridge,40.)*1.5;
      vec3 e = base + fil;
      // after the parting: heaven = pale luminous gold, earth = dark ink with embers
      vec3 heaven = mix(vec3(.55,.36,.2)*.35, vec3(1.,.9,.72)*1.6, pow(ridge,8.));
      vec3 earth  = vec3(.004,.006,.015) + vec3(1.,.25,.05)*pow(ridge,18.)*1.6;
      e = mix(e, mix(earth, heaven, up), divideK);
      // light from the central seam
      e += gold * divideK * exp(-abs(side)*2.2) * .5;
      float a = d*dt*2.2;
      col += T * e * a;
      T *= exp(-a*2.6);
      if(T < .02) break;
    }
    t += dt;
  }

  // deep-space starfield / flying dust (streaks outward as we travel)
  vec3 bg = vec3(0.);
  for(int k=0;k<3;k++){
    float fk = float(k);
    float zz = fract(fk/3. + L*.06);
    float sc = mix(26., 2.5, zz);
    bg += dustLayer(uv, L, sc, 0., vec3(.8,.85,1.), fk*3.1) * smoothstep(0.,.3,zz)*smoothstep(1.,.7,zz) * .6;
  }
  col += bg * T * smoothstep(.5, 3., L);

  // the genesis spark
  float sp = smoothstep(0.4, 0.85, L) * (1. - .75*smoothstep(1.2, 6., L));
  float r2 = dot(uv,uv);
  col += vec3(1.,.86,.62) * sp * (.00012/(r2+.00004));
  col += vec3(1.,.7,.4) * sp * exp(-abs(uv.y)*260.) * exp(-abs(uv.x)*2.2) * 2.5; // anamorphic streak
  col += vec3(1.,.9,.7) * exp(-(L-.8)*(L-.8)*40.) * exp(-r2*14.) * 1.2;         // birth flash

  // the horizon seam: heaven and earth part
  float hy = uv.y;
  float seam = divideK * (1. + 3.*exp(-max(L-9.5,0.)*2.5)*step(9.5,L));
  float gapW = .003 + divideK*.02*(1.+max(L-9.5,0.)*.4);
  col += vec3(1.,.78,.45) * seam * (exp(-abs(hy)/gapW)*1.6 + exp(-abs(hy)*14.)*.12);
  col += vec3(1.,.9,.75) * seam * exp(-abs(hy)*500.) * exp(-abs(uv.x)*.8) * 4.;

  // the three primordial deities: three lights ignite in the high heavens
  vec2 gp[3]; gp[0] = vec2(0.,.33); gp[1] = vec2(-.36,.21); gp[2] = vec2(.36,.21);
  for(int i=0;i<3;i++){
    float ti = 12. + float(i)*.6;
    float a = smoothstep(ti, ti+.25, L);
    float fl = 1. + 2.5*exp(-(L-ti)*4.)*step(ti,L);
    vec2 d = uv - gp[i];
    float rr = length(d);
    vec3 c = vec3(1.,.93,.8);
    col += c * a * fl * (.00035/(rr*rr+.00006));
    col += c * a * fl * (exp(-abs(d.y)*400.)*exp(-abs(d.x)*9.) + exp(-abs(d.x)*400.)*exp(-abs(d.y)*16.)) * .8;
  }
  // links between the three (a faint sacred triangle)
  float tri = smoothstep(13.4, 14.4, L);
  if(tri > 0.){
    for(int i=0;i<3;i++){
      vec2 a = gp[i], b = gp[(i+1)%3];
      vec2 pa = uv-a, ba = b-a; float h = sat(dot(pa,ba)/dot(ba,ba));
      col += vec3(1.,.8,.5) * tri * exp(-length(pa-ba*h)*700.) * .5;
    }
  }

  fragColor = vec4(col, 1.);
}
