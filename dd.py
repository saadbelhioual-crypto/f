import importlib
import os
import zipfile
from pathlib import Path
import shutil
import sys

def save_library_files_to_zip(library_name, output_zip_name=None):
    """
    استخراج وحفظ جميع ملفات مكتبة Python في ملف ZIP
    
    المعاملات:
        library_name: اسم المكتبة المطلوبة
        output_zip_name: اسم ملف ZIP الناتج (اختياري)
    """
    
    if output_zip_name is None:
        output_zip_name = f"{library_name}_files.zip"
    
    try:
        # 1. استيراد المكتبة
        print(f"[1/5] جاري استيراد المكتبة: {library_name}...")
        library = importlib.import_module(library_name)
        
        # 2. الحصول على مسار المكتبة
        try:
            library_path = Path(library.__file__).resolve()
        except AttributeError:
            print(f"⚠️ المكتبة {library_name} ليس لها ملف مادي (قد تكون مدمجة في Python)")
            return False
        
        print(f"[2/5] تم العثور على المكتبة في المسار: {library_path}")
        
        # 3. تحديد المجلد الرئيسي للمكتبة
        if library_path.name.endswith('.py'):
            # ملف بايثون فردي
            library_dir = library_path.parent
            files_to_zip = [library_path]
            print(f"[3/5] مكتبة من ملف واحد: {library_path.name}")
        else:
            # مجلد مكتبة كامل
            library_dir = library_path.parent / library_path.stem
            if not library_dir.exists():
                library_dir = library_path.parent
            
            # تجميع جميع ملفات Python والمستندات
            files_to_zip = []
            extensions = ['*.py', '*.pyc', '*.txt', '*.md', '*.json', '*.ini', '*.cfg', '*.pyd', '*.so', '*.dll']
            
            for ext in extensions:
                files_to_zip.extend(library_dir.rglob(ext))
            
            # إضافة ملف __init__.py إذا وجد
            init_file = library_dir / '__init__.py'
            if init_file.exists() and init_file not in files_to_zip:
                files_to_zip.append(init_file)
            
            print(f"[3/5] تم العثور على {len(files_to_zip)} ملف في مجلد المكتبة")
        
        # 4. إنشاء ملف ZIP
        print(f"[4/5] جاري إنشاء ملف ZIP: {output_zip_name}...")
        
        with zipfile.ZipFile(output_zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files_to_zip:
                try:
                    # حساب المسار النسبي داخل ملف ZIP
                    arcname = file_path.relative_to(library_dir.parent) if library_dir.parent != file_path.parent else file_path.name
                    zipf.write(file_path, arcname)
                    print(f"  ✓ تم إضافة: {arcname}")
                except Exception as e:
                    print(f"  ✗ فشل إضافة {file_path.name}: {e}")
        
        # 5. عرض معلومات عن الملف الناتج
        zip_size = Path(output_zip_name).stat().st_size
        print(f"\n[5/5] ✅ تم الحفظ بنجاح!")
        print(f"📦 اسم الملف: {output_zip_name}")
        print(f"📏 حجم الملف: {zip_size:,} bytes ({zip_size / 1024:.2f} KB)")
        print(f"📁 المسار الكامل: {Path(output_zip_name).absolute()}")
        
        return True
        
    except ImportError:
        print(f"❌ خطأ: المكتبة '{library_name}' غير موجودة أو غير مثبتة")
        print("💡 قم بتثبيتها أولاً باستخدام الأمر:")
        print(f"   pip install {library_name}")
        return False
    except Exception as e:
        print(f"❌ خطأ غير متوقع: {e}")
        return False

def main():
    """
    الوظيفة الرئيسية - تشغيل الكود
    """
    print("=" * 60)
    print("📚 أداة حفظ ملفات مكتبات Python في ملف ZIP")
    print("=" * 60)
    
    # اسم المكتبة المطلوبة (يمكنك تغييره حسب رغبتك)
    library_name = "XcT_x_Team_gen"
    
    # اسم ملف ZIP الناتج (اختياري)
    output_zip = f"{library_name}_archive.zip"
    
    print(f"\n🎯 المكتبة المستهدفة: {library_name}")
    print(f"💾 اسم ملف الإخراج: {output_zip}\n")
    
    # تشغيل عملية الحفظ
    success = save_library_files_to_zip(library_name, output_zip)
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 عملية استخراج وحفظ الملفات اكتملت بنجاح!")
        print("=" * 60)
        
        # عرض محتويات ملف ZIP
        print("\n📋 محتويات ملف ZIP:")
        with zipfile.ZipFile(output_zip, 'r') as zipf:
            for i, name in enumerate(zipf.namelist()[:10], 1):  # عرض أول 10 ملفات فقط
                print(f"   {i}. {name}")
            if len(zipf.namelist()) > 10:
                print(f"   ... و {len(zipf.namelist()) - 10} ملفات أخرى")
    else:
        print("\n❌ فشلت عملية حفظ الملفات")

if __name__ == "__main__":
    main()
