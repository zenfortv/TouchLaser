// Brightness to black and white bands: contours.py outlines every band edge, so one pass gives
// all the contour levels. One level is a plain threshold. Wipe hides part of the image; engrave
// is a wipe too, but scans.py draws it from the whole mask.
uniform vec4 uA;   // levels, shift, floor (threshold at one level), contrast
uniform vec3 uB;   // invert, wipe (0 off, 1 down, 2 up, 3 right, 4 left, 5 radar, 6 iris, 7 engrave), phase 0-2
out vec4 fragColor;

float along(float axis)
{
	if (axis < 1.5) return 1.0 - vUV.t;
	if (axis < 2.5) return vUV.t;
	if (axis < 3.5) return vUV.s;
	if (axis < 4.5) return 1.0 - vUV.s;
	vec2 d = vUV.st - 0.5;
	if (axis < 5.5) return fract(atan(d.x, d.y) / 6.28318531 + 1.0);   // clockwise from twelve
	return length(d) * 1.41421356;                                     // centre to corners
}

void main()
{
	float v = texture(sTD2DInputs[0], vUV.st).r;
	v = clamp((v - 0.5) * uA.w + 0.5, 0.0, 1.0);
	if (uB.x > 0.5) v = 1.0 - v;

	float m = step(uA.z, v);                                  // below the floor stays black
	if (uA.x > 1.5) m *= step(0.5, fract(v * uA.x + uA.y));

	if (uB.y > 0.5 && uB.y < 6.5) {
		float p = mod(uB.z, 2.0);                             // 0-1 reveals, 1-2 hides
		float c = along(uB.y);
		m *= p < 1.0 ? step(c, p) : step(p - 1.0, c);
	}
	fragColor = TDOutputSwizzle(vec4(m, m, m, 1.0));
}
