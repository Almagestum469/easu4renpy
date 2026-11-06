# -*- coding: utf-8 -*-
# EASU texture magnification for Ren'Py 8.5.3 (single pass, no RCAS).
# Port of FsrEasuSetF / FsrEasuTapF / FsrEasuF from:
# https://github.com/GPUOpen-Effects/FidelityFX-FSR/blob/master/ffx-fsr/ffx_fsr1.h
# Changes: explicit texel-center reads, exact reciprocal/rsqrt, UV-based
# positioning, derivative magnification test, conservative alpha fallback.
#
# Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# INSTALL: Copy this file to game/. Disable/remove the SGSR implementation
# and other overrides of renpy.texture, including their orphan .rpyc files.
# Restart completely. No layer transform or gui.init change is needed.
# This uses an unofficial override of a reserved Ren'Py shader part.
# Affects UI/intermediate textures using renpy.texture too; not all movies,
# transitions or Live2D. Atlas subrect bounds are unavailable: neighboring
# images can bleed into samples. Use dedicated textures or sufficient gutters.
# GLSL ES requires derivatives, as does the existing SGSR implementation.

init 999 python:
    EASU_ENABLED = True
    # Diagnostic: magenta means the magnification path was reached; alpha
    # fallback may still use native filtering when this diagnostic is off.
    EASU_DEBUG_MAGNIFICATION = False

    if EASU_ENABLED:
        easu_functions = r"""
            float easu_luma(vec3 c) {
                return c.g + 0.5 * (c.r + c.b);
            }

            vec4 easu_read(sampler2D image, vec2 ip, vec2 size) {
                vec2 p = clamp(ip, vec2(0.0), size - vec2(1.0));
                return texture2D(image, (p + vec2(0.5)) / size, 0.0);
            }

            // Bilinear weight is supplied directly instead of four bools.
            void easu_set(inout vec2 dir, inout float len, float w,
                          float a, float b, float c, float d, float e) {
                float dx = d - b;
                float dy = e - a;
                dir += vec2(dx, dy) * w;
                float lx = clamp(abs(dx) / max(max(abs(d-c), abs(c-b)),
                                               0.00000001), 0.0, 1.0);
                float ly = clamp(abs(dy) / max(max(abs(e-c), abs(c-a)),
                                               0.00000001), 0.0, 1.0);
                len += (lx * lx + ly * ly) * w;
            }

            void easu_tap(inout vec3 ac, inout float aw, vec2 off,
                          vec2 dir, vec2 len, float lob, float clp, vec3 c) {
                vec2 v = vec2(dot(off, dir),
                              dot(off, vec2(-dir.y, dir.x))) * len;
                float d2 = min(dot(v, v), clp);
                float wb = 0.4 * d2 - 1.0;
                float wa = lob * d2 - 1.0;
                wb *= wb;
                wa *= wa;
                wb = 1.5625 * wb - 0.5625;
                float w = wb * wa;
                ac += c * w;
                aw += w;
            }

            vec4 easu_filter(sampler2D image, vec2 uv, vec2 size, float bias) {
                // Derivatives must be evaluated before non-uniform branches.
                vec2 dx = dFdx(uv) * size;
                vec2 dy = dFdy(uv) * size;
                // Largest singular value of the UV Jacobian: avoid filtering
                // mixed magnification/minification, including rotated meshes.
                float xx = dot(dx, dx);
                float yy = dot(dy, dy);
                float xy = dot(dx, dy);
                float density = sqrt(max(0.0, 0.5 * (xx + yy +
                    sqrt(max(0.0, (xx-yy)*(xx-yy) + 4.0*xy*xy)))));
                vec4 base = texture2D(image, uv, bias);
                if (density >= 0.98 || density <= 0.00001) return base;
                if (__DEBUG__ != 0) return vec4(base.a, 0.0, base.a, base.a);

                // UV already contains the input/output mapping, including
                // half-pixel alignment; FsrEasuCon is therefore unnecessary.
                vec2 p = uv * size - vec2(0.5);
                vec2 ip = floor(p);
                vec2 f = p - ip;
                //       b c
                //     e f g h
                //     i j k l
                //       n o
                vec4 b = easu_read(image, ip + vec2( 0.0,-1.0), size);
                vec4 c = easu_read(image, ip + vec2( 1.0,-1.0), size);
                vec4 e = easu_read(image, ip + vec2(-1.0, 0.0), size);
                vec4 q = easu_read(image, ip + vec2( 0.0, 0.0), size);
                vec4 g = easu_read(image, ip + vec2( 1.0, 0.0), size);
                vec4 h = easu_read(image, ip + vec2( 2.0, 0.0), size);
                vec4 i = easu_read(image, ip + vec2(-1.0, 1.0), size);
                vec4 j = easu_read(image, ip + vec2( 0.0, 1.0), size);
                vec4 k = easu_read(image, ip + vec2( 1.0, 1.0), size);
                vec4 l = easu_read(image, ip + vec2( 2.0, 1.0), size);
                vec4 n = easu_read(image, ip + vec2( 0.0, 2.0), size);
                vec4 o = easu_read(image, ip + vec2( 1.0, 2.0), size);

                // Official EASU assumes opaque RGB. At transparent boundaries
                // keep Ren'Py's premultiplied native result. Do not run the
                // negative-lobe RGB filter across different alpha coverage.
                float minAlpha = min(min(min(b.a,c.a),min(e.a,q.a)),
                                     min(min(g.a,h.a),min(i.a,j.a)));
                minAlpha = min(minAlpha, min(min(k.a,l.a),min(n.a,o.a)));
                if (minAlpha < 0.9999 || base.a < 0.9999) return base;

                float bl = easu_luma(b.rgb), cl = easu_luma(c.rgb);
                float el = easu_luma(e.rgb), fl = easu_luma(q.rgb);
                float gl = easu_luma(g.rgb), hl = easu_luma(h.rgb);
                float il = easu_luma(i.rgb), jl = easu_luma(j.rgb);
                float kl = easu_luma(k.rgb), ll = easu_luma(l.rgb);
                float nl = easu_luma(n.rgb), ol = easu_luma(o.rgb);
                vec2 dir = vec2(0.0);
                float len = 0.0;
                easu_set(dir,len,(1.0-f.x)*(1.0-f.y),bl,el,fl,gl,jl);
                easu_set(dir,len,     f.x*(1.0-f.y),cl,fl,gl,hl,kl);
                easu_set(dir,len,(1.0-f.x)*     f.y,fl,il,jl,kl,nl);
                easu_set(dir,len,     f.x*     f.y,gl,jl,kl,ll,ol);
                float d2 = dot(dir, dir);
                if (d2 < 1.0 / 32768.0) dir = vec2(1.0, 0.0);
                else dir *= inversesqrt(d2);
                len *= 0.5;
                len *= len;
                float stretch = dot(dir,dir) / max(abs(dir.x),abs(dir.y));
                vec2 len2 = vec2(1.0 + (stretch-1.0)*len, 1.0-0.5*len);
                float lob = 0.5 - 0.29 * len;
                float clp = 1.0 / lob;
                vec3 ac = vec3(0.0);
                float aw = 0.0;
                easu_tap(ac,aw,vec2( 0.0,-1.0)-f,dir,len2,lob,clp,b.rgb);
                easu_tap(ac,aw,vec2( 1.0,-1.0)-f,dir,len2,lob,clp,c.rgb);
                easu_tap(ac,aw,vec2(-1.0, 1.0)-f,dir,len2,lob,clp,i.rgb);
                easu_tap(ac,aw,vec2( 0.0, 1.0)-f,dir,len2,lob,clp,j.rgb);
                easu_tap(ac,aw,vec2( 0.0, 0.0)-f,dir,len2,lob,clp,q.rgb);
                easu_tap(ac,aw,vec2(-1.0, 0.0)-f,dir,len2,lob,clp,e.rgb);
                easu_tap(ac,aw,vec2( 1.0, 1.0)-f,dir,len2,lob,clp,k.rgb);
                easu_tap(ac,aw,vec2( 2.0, 1.0)-f,dir,len2,lob,clp,l.rgb);
                easu_tap(ac,aw,vec2( 2.0, 0.0)-f,dir,len2,lob,clp,h.rgb);
                easu_tap(ac,aw,vec2( 1.0, 0.0)-f,dir,len2,lob,clp,g.rgb);
                easu_tap(ac,aw,vec2( 1.0, 2.0)-f,dir,len2,lob,clp,o.rgb);
                easu_tap(ac,aw,vec2( 0.0, 2.0)-f,dir,len2,lob,clp,n.rgb);
                if (abs(aw) < 0.00001) return base;
                vec3 lo = min(min(q.rgb,g.rgb),min(j.rgb,k.rgb));
                vec3 hi = max(max(q.rgb,g.rgb),max(j.rgb,k.rgb));
                vec3 rgb = clamp(ac / aw, lo, hi);
                return vec4(clamp(rgb,vec3(0.0),vec3(base.a)),base.a);
            }
        """
        easu_functions = easu_functions.replace(
            "__DEBUG__", "1" if EASU_DEBUG_MAGNIFICATION else "0")
        renpy.register_shader(
            "renpy.texture",
            variables="""
                uniform float u_lod_bias;
                uniform sampler2D tex0;
                uniform vec2 res0;
                attribute vec2 a_tex_coord;
                varying vec2 v_tex_coord;
            """,
            vertex_200="""
                v_tex_coord = a_tex_coord;
            """,
            fragment_functions=easu_functions,
            fragment_200="""
                gl_FragColor = easu_filter(tex0,v_tex_coord,res0,u_lod_bias);
            """
        )
