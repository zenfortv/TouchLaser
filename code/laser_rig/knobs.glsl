// All the Video Knobs in one pass, from knobs.py's data image, with the Text TOP on top.
// Input 0: row 0 x, y, radius or half width, position; row 1 kind (0 knob, 1 button), lit, half height.
out vec4 fragColor;

const vec3 BACK = vec3(0.145);
const vec3 TRACK = vec3(0.30);
const vec3 BODY = vec3(0.105);
const vec3 LIGHT = vec3(0.72);
const vec3 RED = vec3(0.84, 0.05, 0.05);
const vec3 STRIP = vec3(0.02);
const float START = 2.35619449;   // the arc runs 135 degrees either side of twelve o'clock
const float SWEEP = 4.71238898;

float inside(float d, float r)
{
	return smoothstep(r + 0.7, r - 0.7, d);
}

float box(vec2 d, vec2 half_size)
{
	vec2 q = abs(d) - half_size;
	return inside(max(q.x, q.y), 0.0);
}

vec3 knob(vec3 col, vec2 d, float r, float position, float lit)
{
	col = mix(col, STRIP, box(d - vec2(0.0, -r - 14.0), vec2(r + 12.0, 8.0)));
	float dist = length(d);
	if (dist > r + 2.0) return col;
	float t = (atan(d.x, d.y) + START) / SWEEP;
	float ring = inside(abs(dist - r * 0.92), r * 0.06);
	if (t >= 0.0 && t <= 1.0)
		col = mix(col, t <= position ? (lit > 0.5 ? RED : LIGHT) : TRACK, ring);
	col = mix(col, BODY, inside(dist, r * 0.76));
	float at = position * SWEEP - START;
	vec2 hand = vec2(sin(at), cos(at));
	float across = abs(dot(d, vec2(hand.y, -hand.x)));
	float along = dot(d, hand);
	if (along > r * 0.58 && along < r * 0.76) col = mix(col, RED, inside(across, 1.3));
	return col;
}

vec3 button(vec3 col, vec2 d, vec2 half_size, float lit)
{
	col = mix(col, lit > 0.5 ? RED : TRACK, box(d, half_size));
	return mix(col, lit > 0.5 ? RED : BODY, box(d, half_size - 1.0));
}

void main()
{
	vec2 px = vUV.st * uTDOutputInfo.res.zw;
	vec3 col = BACK;
	int n = textureSize(sTD2DInputs[0], 0).x;
	for (int i = 0; i < n; i++) {
		vec4 a = texelFetch(sTD2DInputs[0], ivec2(i, 0), 0);
		vec4 b = texelFetch(sTD2DInputs[0], ivec2(i, 1), 0);
		vec2 d = px - a.xy;
		col = b.x < 0.5 ? knob(col, d, a.z, a.w, b.y) : button(col, d, vec2(a.z, b.z), b.y);
	}
	vec4 words = texture(sTD2DInputs[1], vUV.st);
	col = col * (1.0 - words.a) + words.rgb;
	fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
