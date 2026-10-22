using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
class IconBuilder {
    static void Main(string[] args) {
        using(Bitmap bitmap = new Bitmap(64,64)) {
            using(Graphics g = Graphics.FromImage(bitmap)) {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.Clear(Color.Transparent);
                using(SolidBrush brush = new SolidBrush(ColorTranslator.FromHtml(args[1]))) g.FillEllipse(brush,2,2,60,60);
                using(Font font = new Font("Segoe UI", args[2]=="e"?42:20,FontStyle.Bold,GraphicsUnit.Pixel))
                using(SolidBrush brush = new SolidBrush(Color.White)) {
                    StringFormat format = new StringFormat();
                    format.Alignment = StringAlignment.Center; format.LineAlignment = StringAlignment.Center;
                    g.DrawString(args[2],font,brush,new RectangleF(0,0,64,62),format);
                }
            }
            using(Icon icon = Icon.FromHandle(bitmap.GetHicon()))
            using(FileStream file = File.Create(args[0])) icon.Save(file);
        }
    }
}
