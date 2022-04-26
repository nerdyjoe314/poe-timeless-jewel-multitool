from PIL import Image

infile = Image.open("Colors.png")
(w, h) = infile.size
manip = infile.convert('RGB')
for i in range(w):
    for j in range(h):
        val = manip.getpixel((i,j))
        manip.putpixel((i,j), (0,0,0))
        if sum(val)<260:
            continue
        d1= val[0]-val[1]
        d2= val[1]-val[2]
        if d1<0 or d2<0:
            continue
        manip.putpixel((i,j), (255,255,255))
manip.save("filtered.png")