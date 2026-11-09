# A neck running straight up while its 'up' is world Y (quadruped settings): no twist along the neck / head
exec(open("fakemaya.py").read())
import numpy as np
from gus_rigtool.builder import mathx
for name, pts, up in (("vertical neck, up Y", [[0, 150, 5], [0, 160, 6], [0, 170, 6.5], [0, 178, 7]], [0, 1, 0]),
                      ("forward neck, up Z", [[0, 150, 0], [0, 152, 10], [0, 153, 20]], [0, 0, 1]),
                      ("normal case", [[0, 100, 0], [0, 100, 20], [0, 105, 40]], [0, 1, 0])):
    ms = mathx.chain_matrices(pts, "X", "Y", "world", up)
    ys = [np.array(m[4:7]) for m in ms]
    worst = max(np.degrees(np.arccos(np.clip(np.dot(a, b), -1, 1))) for a, b in zip(ys, ys[1:]))
    print("%-22s up axis used %s | biggest change of the side axis along the chain: %.1f deg"
          % (name, mathx.steady_up(pts, up), worst))
