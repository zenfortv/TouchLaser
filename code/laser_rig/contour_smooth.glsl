// Stability: blends each frame with the last, so video noise does not shake the contours.
// Input 0 = brightness, input 1 = last result.
uniform float uStability;
out vec4 fragColor;

void main()
{
	float now = texture(sTD2DInputs[0], vUV.st).r;
	float last = texture(sTD2DInputs[1], vUV.st).r;
	float v = mix(now, last, uStability);
	fragColor = TDOutputSwizzle(vec4(v, v, v, 1.0));
}
