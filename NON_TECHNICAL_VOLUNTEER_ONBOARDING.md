# LNRS Tech for Good: Complete Volunteer Onboarding Checklist 📋

*A step-by-step guide for joining the Tackle Hunger charity validation project*

---

## 🎯 **What You'll Be Doing**
You'll help **families find food assistance** by keeping charity information accurate and up-to-date. Your work ensures people can find working phone numbers, correct addresses, and current hours for food banks and soup kitchens.

---

## ✅ **Pre-Requirements Checklist**

### **Step 1: Check Your Computer** 🖥️
- [ ] **Windows, Mac, or Linux computer** (any will work)
- [ ] **Reliable internet connection**
- [ ] **At least 2GB free disk space**

### **Step 2: Install Python** 🐍
*Don't worry - this is easier than it sounds!*

**For Windows:**
1. [ ] Go to [python.org/downloads](https://python.org/downloads)
2. [ ] Click the big yellow **"Download Python"** button
3. [ ] Run the downloaded file
4. [ ] ⚠️ **IMPORTANT**: Check the box "Add Python to PATH" during installation
5. [ ] Click "Install Now"
6. [ ] Restart your computer when done

**For Mac:**
1. [ ] Go to [python.org/downloads](https://python.org/downloads)
2. [ ] Download the macOS installer
3. [ ] Run the downloaded .pkg file
4. [ ] Follow the installation wizard

**For Linux:**
```bash
# Ubuntu/Debian:
sudo apt update && sudo apt install python3 python3-pip

# Other distributions: use your package manager
```

### **Step 3: Install Git** 📦
*This helps you download and manage the project code*

**For Windows:**
1. [ ] Go to [git-scm.com](https://git-scm.com)
2. [ ] Click "Download for Windows"
3. [ ] Run the installer with default settings
4. [ ] Restart your computer

**For Mac:**
1. [ ] Install using Homebrew: `brew install git`
2. [ ] OR download from [git-scm.com](https://git-scm.com)

**For Linux:**
```bash
# Ubuntu/Debian:
sudo apt install git

# Other distributions: use your package manager
```

---

## 🚀 **Project Setup (The Easy Way)**

### **Step 4: Download the Project** 📥
1. [ ] **Open your terminal/command prompt:**
   - **Windows**: Press `Windows + R`, type `cmd`, press Enter
   - **Mac**: Press `Cmd + Space`, type `terminal`, press Enter
   - **Linux**: Press `Ctrl + Alt + T`

2. [ ] **Create a workspace folder:**
   ```bash
   # Copy and paste this line, then press Enter:
   mkdir tackle-hunger-workspace
   cd tackle-hunger-workspace
   ```

3. [ ] **Download the project:**
   ```bash
   # Copy and paste this line, then press Enter:
   git clone https://github.com/TackleHunger/LNRS-Tech-for-Good-AI-Charity-Validation.git
   ```

4. [ ] **Enter the project folder:**
   ```bash
   # Copy and paste this line, then press Enter:
   cd LNRS-Tech-for-Good-AI-Charity-Validation
   ```

### **Step 5: Automatic Setup** 🎉
*This installs everything you need automatically*

1. [ ] **Run the setup script:**
   ```bash
   # Copy and paste this line, then press Enter:
   python scripts/setup_dev_environment.py
   ```

2. [ ] **Wait for setup to complete** - You should see:
   - ✅ Dependencies installed
   - ✅ Environment file created
   - 🎉 Setup complete!

**If you see errors:** 
- Try `python3` instead of `python`
- Make sure you're in the project folder
- Ask for help in your team channel

---

## 🔑 **Get Your API Token**

### **Step 6: Request Access** 
*You need this to actually work with charity data*

1. [ ] **Contact your LNRS Tech for Good team lead**
2. [ ] **Ask for the `AI_SCRAPING_TOKEN`**
3. [ ] **Tell them you've completed the setup steps**

### **Step 7: Add Your Token**
*Once you receive the token:*

1. [ ] **Find the `.env` file** in your project folder
2. [ ] **Open it with any text editor** (Notepad, TextEdit, etc.)
3. [ ] **Replace `your_ai_scraping_token_here` with your actual token**
4. [ ] **Save the file**

**Example:**
```
# Before:
AI_SCRAPING_TOKEN=your_ai_scraping_token_here

# After:
AI_SCRAPING_TOKEN=abc123your_real_token_here
```

---

## 🧪 **Test Your Setup**

### **Step 8: Verify Everything Works** ✅

1. [ ] **Test connectivity:**
   ```bash
   # Copy and paste this line:
   python scripts/test_connectivity.py
   ```
   *You should see all green checkmarks ✅*

2. [ ] **Run the test suite:**
   ```bash
   # Copy and paste this line:
   python -m pytest tests/
   ```
   *You should see "passed" for all tests*

**If tests fail:** Don't panic! Ask your team lead for help.

---

## 📚 **Learn the Workflow**

### **Step 9: Read the Guide** 📖
1. [ ] **Open and read:** `HOW_TO_VALIDATE_CHARITIES.md`
2. [ ] **Understand what you'll be doing:**
   - Verify charity addresses and phone numbers
   - Update outdated information
   - Add new charities to help more families

### **Step 10: Practice Run** 🎯
*Ask your team lead to walk through your first charity validation*

1. [ ] **Schedule a 15-minute call** with someone experienced
2. [ ] **Do your first validation together**
3. [ ] **Ask questions** about anything unclear

---

## 🆘 **Getting Help**

### **Common Issues & Solutions** 🔧

**"Python not found" error:**
- Restart your computer after installing Python
- Try `python3` instead of `python`

**"Git not found" error:**
- Restart your computer after installing Git
- Make sure Git was installed correctly

**"Permission denied" errors:**
- On Mac/Linux, try adding `sudo` before commands
- Ask your team lead for help

**"Tests failing" with token:**
- Double-check your token in the `.env` file
- Make sure there are no extra spaces
- Ask team lead to verify the token

### **Where to Get Help** 🤝
1. **Team Channel** - Ask in your LNRS Tech for Good group
2. **Team Lead** - Contact the person who invited you
3. **GitHub Issues** - Check if others have the same problem
4. **Documentation** - Look in the `docs/` folder

---

## 🎉 **You're Ready!**

### **Final Checklist** ✨
- [ ] Python installed and working
- [ ] Git installed and working
- [ ] Project downloaded and setup complete
- [ ] API token received and configured
- [ ] Tests passing
- [ ] Documentation read
- [ ] First practice session completed

### **Your Impact** 🍽️
Once complete, you'll be helping:
- **Families find food faster** with accurate charity information
- **Food banks reach more people** by keeping their details current
- **Communities stay fed** by expanding the network of assistance

---

## 💡 **Pro Tips for Success**

1. **Take breaks** - Don't try to do everything at once
2. **Ask questions** - The team wants to help you succeed
3. **Start small** - Validate a few charities before tackling many
4. **Document issues** - Note anything confusing for future volunteers
5. **Celebrate wins** - Every charity you validate helps real families!

---

**🎯 Ready to make a difference? You've got this!** 

*Questions? Don't hesitate to reach out to your team lead or ask in the group chat.*
