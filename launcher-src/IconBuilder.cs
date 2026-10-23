using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.IO;

// Repeatable native artwork on a transparent 256-unit canvas.
class IconBuilder {
    static readonly int[] Sizes = {16,20,24,32,40,48,64,96,128,256};
    static Color C(string hex) { return ColorTranslator.FromHtml(hex); }
    static GraphicsPath Round(float x,float y,float w,float h,float r) {
        GraphicsPath p=new GraphicsPath();
        p.AddArc(x,y,r*2,r*2,180,90); p.AddArc(x+w-r*2,y,r*2,r*2,270,90);
        p.AddArc(x+w-r*2,y+h-r*2,r*2,r*2,0,90); p.AddArc(x,y+h-r*2,r*2,r*2,90,90);
        p.CloseFigure(); return p;
    }
    static void Gradient(Graphics g,GraphicsPath p,RectangleF b,string a,string z,float angle) {
        using(LinearGradientBrush brush=new LinearGradientBrush(b,C(a),C(z),angle)) g.FillPath(brush,p);
    }
    static void Panel(Graphics g,float x,float y,float w,float h,float r,string a,string z,float angle) {
        using(GraphicsPath p=Round(x,y,w,h,r)) Gradient(g,p,new RectangleF(x,y,w,h),a,z,angle);
    }
    static void Letter(Graphics g,string text,float centerX,float centerY,float height) {
        using(FontFamily family=new FontFamily("Segoe UI"))
        using(GraphicsPath glyph=new GraphicsPath()) {
            glyph.AddString(text,family,(int)FontStyle.Bold,80,PointF.Empty,StringFormat.GenericTypographic);
            RectangleF b=glyph.GetBounds(); float scale=height/b.Height;
            using(Matrix m=new Matrix()) { m.Translate(-b.X,-b.Y); glyph.Transform(m); }
            using(Matrix m=new Matrix()) { m.Scale(scale,scale); glyph.Transform(m); }
            RectangleF scaled=glyph.GetBounds();
            using(Matrix m=new Matrix()) { m.Translate(centerX-scaled.Width/2,centerY-height/2); glyph.Transform(m); }
            using(SolidBrush white=new SolidBrush(Color.White)) g.FillPath(white,glyph);
        }
    }
    static void ChartBar(Graphics g,float x,float y,float w,float h,string a,string b,bool small) {
        Panel(g,x,y,w,h,15,a,b,72);
        if(!small) using(GraphicsPath p=Round(x+.8f,y+.8f,w-1.6f,h-1.6f,14.2f))
        using(Pen edge=new Pen(Color.FromArgb(35,255,255,255),1.2f)) g.DrawPath(edge,p);
    }
    static void Cylinder(Graphics g,float y,string a,string b,string capA,string capB,bool small) {
        const float x=32,w=192,h=92,e=48;
        using(GraphicsPath body=new GraphicsPath()) {
            body.AddLine(x,y+e/2,x,y+h-e/2);
            body.AddArc(x,y+h-e,w,e,180,-180);
            body.AddLine(x+w,y+h-e/2,x+w,y+e/2);
            body.AddArc(x,y,w,e,0,-180);body.CloseFigure();
            Gradient(g,body,new RectangleF(x,y,w,h),a,b,25);
        }
        using(GraphicsPath cap=new GraphicsPath()) {
            cap.AddEllipse(x,y,w,e);
            Gradient(g,cap,new RectangleF(x,y,w,e),capA,capB,15);
        }
        if(!small) using(Pen rim=new Pen(Color.FromArgb(85,223,235,255),1.5f)) g.DrawEllipse(rim,x+1,y+1,w-2,e-2);
    }
    static void Artwork(Graphics g,bool sql,bool small) {
        if(sql) {
            // Three actual cylindrical data layers form the complete silhouette.
            Cylinder(g,148,"#5052D4","#39308E","#8C8AEF","#6861D6",small);
            Cylinder(g,82,"#566BE6","#4142B1","#97ABFA","#7778E6",small);
            Cylinder(g,16,"#6285EE","#4F55CC","#A8CAFF","#8495F0",small);
            Letter(g,"S",128,166,small?84:82);
        } else {
            // The rising chart is the icon, with D printed directly on its front bar.
            ChartBar(g,150,16,88,224,"#61D69F","#11825C",small);
            ChartBar(g,88,64,94,176,"#39CC99","#087F59",small);
            ChartBar(g,18,112,116,128,"#17B788","#076D50",small);
            Letter(g,"D",76,177,small?72:70);
        }
    }
    static Bitmap Render(bool sql,int size) {
        // Render every frame separately, simplifying highlights below 32 px.
        int raster=size<=64?size*4:size*2;
        using(Bitmap large=new Bitmap(raster,raster,PixelFormat.Format32bppArgb)) {
            using(Graphics g=Graphics.FromImage(large)) {
                g.Clear(Color.Transparent); g.SmoothingMode=SmoothingMode.AntiAlias; g.PixelOffsetMode=PixelOffsetMode.HighQuality;
                g.ScaleTransform(raster/256f,raster/256f); Artwork(g,sql,size<32);
            }
            Bitmap result=new Bitmap(size,size,PixelFormat.Format32bppArgb);
            using(Graphics g=Graphics.FromImage(result)) {
                g.CompositingMode=CompositingMode.SourceCopy; g.InterpolationMode=InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode=PixelOffsetMode.HighQuality;
                g.DrawImage(large,new Rectangle(0,0,size,size),0,0,raster,raster,GraphicsUnit.Pixel);
            }
            return result;
        }
    }
    static byte[] Frame(Bitmap image,int size) {
        using(MemoryStream stream=new MemoryStream()) {
            if(size==256) { image.Save(stream,ImageFormat.Png); return stream.ToArray(); }
            // DIB frames remain compatible with older Win32 icon consumers.
            using(BinaryWriter w=new BinaryWriter(stream)) {
                int stride=((size+31)/32)*4;
                w.Write(40);w.Write(size);w.Write(size*2);w.Write((short)1);w.Write((short)32);
                w.Write(0);w.Write(size*size*4+stride*size);w.Write(0);w.Write(0);w.Write(0);w.Write(0);
                for(int y=size-1;y>=0;--y) for(int x=0;x<size;++x) {
                    Color p=image.GetPixel(x,y);w.Write(p.B);w.Write(p.G);w.Write(p.R);w.Write(p.A);
                }
                for(int y=size-1;y>=0;--y) {
                    byte[] row=new byte[stride];
                    for(int x=0;x<size;++x) if(image.GetPixel(x,y).A==0) row[x/8]|=(byte)(128>>(x%8));
                    w.Write(row);
                }
            }
            return stream.ToArray();
        }
    }
    static void SaveIcon(string path,bool sql) {
        List<byte[]> frames=new List<byte[]>();
        foreach(int size in Sizes) using(Bitmap image=Render(sql,size)) frames.Add(Frame(image,size));
        using(BinaryWriter w=new BinaryWriter(File.Create(path))) {
            w.Write((short)0);w.Write((short)1);w.Write((short)Sizes.Length);int offset=6+Sizes.Length*16;
            for(int i=0;i<Sizes.Length;++i) {
                int size=Sizes[i];w.Write((byte)(size==256?0:size));w.Write((byte)(size==256?0:size));
                w.Write((byte)0);w.Write((byte)0);w.Write((short)1);w.Write((short)32);
                w.Write(frames[i].Length);w.Write(offset);offset+=frames[i].Length;
            }
            foreach(byte[] frame in frames) w.Write(frame);
        }
    }
    static void Preview(string directory) {
        using(Bitmap canvas=new Bitmap(1160,620))
        using(Graphics g=Graphics.FromImage(canvas))
        using(Font title=new Font("Segoe UI",24,FontStyle.Bold,GraphicsUnit.Pixel))
        using(Font label=new Font("Segoe UI",17,FontStyle.Regular,GraphicsUnit.Pixel))
        using(Font note=new Font("Segoe UI",14,FontStyle.Regular,GraphicsUnit.Pixel)) {
            g.TextRenderingHint=TextRenderingHint.AntiAliasGridFit;g.Clear(C("#F5F7FA"));
            using(SolidBrush dark=new SolidBrush(C("#182129"))) g.FillRectangle(dark,580,0,580,620);
            for(int side=0;side<2;++side) {
                int left=side*580;
                using(SolidBrush ink=new SolidBrush(side==0?C("#182B35"):C("#F0F6FA"))) {
                    g.DrawString("easyERP",title,ink,left+34,27);
                    g.DrawString(side==0?"Light background":"Dark background",label,ink,left+34,64);
                    for(int kind=0;kind<2;++kind) {
                        int x=left+55+kind*254;
                        using(Bitmap icon=Render(kind==1,192)) g.DrawImageUnscaled(icon,x,117);
                        g.DrawString(kind==0?"Dashboard":"SQLview",label,ink,x+47,330);
                        int cursor=x-4;
                        foreach(int size in new int[]{16,24,32,48,64}) {
                            using(Bitmap icon=Render(kind==1,size)) g.DrawImageUnscaled(icon,cursor,448-size);
                            g.DrawString(size.ToString(),note,ink,cursor,462);cursor+=size+10;
                        }
                    }
                    g.DrawString("Transparent .ico  /  16-256 px  /  10 sizes",note,ink,left+34,563);
                }
            }
            canvas.Save(Path.Combine(directory,"icon-preview.png"),ImageFormat.Png);
        }
    }
    static int Main(string[] args) {
        try {
            if(args.Length!=1) throw new ArgumentException("Usage: IconBuilder <output-directory>");
            Directory.CreateDirectory(args[0]);
            SaveIcon(Path.Combine(args[0],"frontend.ico"),false);SaveIcon(Path.Combine(args[0],"backend.ico"),true);
            using(Bitmap image=Render(false,512)) image.Save(Path.Combine(args[0],"dashboard.png"),ImageFormat.Png);
            using(Bitmap image=Render(true,512)) image.Save(Path.Combine(args[0],"sqlview.png"),ImageFormat.Png);
            Preview(args[0]);return 0;
        } catch(Exception ex) { Console.Error.WriteLine(ex.Message);return 1; }
    }
}
