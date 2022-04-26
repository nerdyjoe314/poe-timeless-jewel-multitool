from PIL import Image

maxip = Image.open("7960.png")
minip = Image.open("7960.png")
#maxip = Image.open("6230.png")
#minip = Image.open("6230.png")
(w, h) = maxip.size
#filenames=["26196.png", "26725.png", "28475.png","31683.png","33631.png","33989.png","34483.png","36634.png","41263.png","54127.png","60735.png","61419.png","61834.png"]
filenames=["2491.png","21984.png","32763.png","46882.png","55190.png",]
for f in filenames:
    nextim=Image.open(f)
    for i in range(w):
        for j in range(h):
            val1 = maxip.getpixel((i,j))
            val2 = nextim.getpixel((i,j))
            val3 = minip.getpixel((i,j))
            valmax= (max([val1,val2]))
            valmin= (min([val3,val2]))
            maxip.putpixel((i,j), valmax)
            minip.putpixel((i,j), valmin)
maxip.save("maxfiltered.png")
minip.save("minfiltered.png")